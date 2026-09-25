"""
Shovel Volume: volumen de roca disponible por pala y priorizacion de frentes.

Reproduce, con datos sinteticos, el calculo diario que sustenta la reunion de
prioridades con el departamento de Produccion en una operacion a cielo abierto:

  1. Consolida el inventario de frentes disponibles por pala.
  2. Convierte BCM in-situ a toneladas y a volumen suelto (LCM).
  3. Calcula la autonomia de cada pala en horas, dado su ritmo de produccion.
  4. Estima el tiempo de ciclo y la productividad real de la flota por frente.
  5. Prioriza frentes combinando volumen disponible y distancia de acarreo.
  6. Reporta el cumplimiento del turno frente a la meta establecida.

Uso:
    python src/generar_datos.py
    python src/shovel_volume.py
"""

import csv
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent
DATOS = BASE / "datos"
SALIDAS = BASE / "salidas"
SALIDAS.mkdir(exist_ok=True)

DENSIDAD = {"ESTERIL": 2.45, "CARBON": 1.35}       # t/m3 in-situ
ESPONJAMIENTO = {"ESTERIL": 1.30, "CARBON": 1.20}  # LCM / BCM

# Ritmo nominal de produccion por pala, en BCM por hora operativa
RITMO_PALA_BCM_H = {"SH-01": 1350, "SH-02": 1350, "SH-03": 980, "SH-04": 980}

# Meta de produccion del turno, en toneladas
META_TURNO_T = {"DIA": 92_000, "NOCHE": 78_000}

# Umbral de autonomia por debajo del cual la pala entra en alerta
AUTONOMIA_CRITICA_H = 24.0


def leer_csv(ruta):
    with open(ruta, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def bcm_a_toneladas(bcm, material):
    """BCM in-situ -> toneladas."""
    return bcm * DENSIDAD[material]


def bcm_a_lcm(bcm, material):
    """BCM in-situ -> LCM (volumen suelto, el que realmente transporta el camion)."""
    return bcm * ESPONJAMIENTO[material]


def calcular_shovel_volume(frentes):
    """Volumen disponible, autonomia y estado de alerta por pala."""
    acum = defaultdict(lambda: {"bcm": 0.0, "ton": 0.0, "lcm": 0.0, "frentes": 0})

    for f in frentes:
        if f["disponible"] != "SI":
            continue
        pala = f["pala_asignada"]
        bcm = float(f["bcm_disponible"])
        mat = f["material"]
        acum[pala]["bcm"] += bcm
        acum[pala]["ton"] += bcm_a_toneladas(bcm, mat)
        acum[pala]["lcm"] += bcm_a_lcm(bcm, mat)
        acum[pala]["frentes"] += 1

    filas = []
    for pala in sorted(acum):
        d = acum[pala]
        ritmo = RITMO_PALA_BCM_H.get(pala, 1000)
        autonomia = d["bcm"] / ritmo if ritmo else 0.0
        filas.append({
            "pala": pala,
            "frentes_disponibles": d["frentes"],
            "bcm_disponible": round(d["bcm"], 0),
            "lcm_disponible": round(d["lcm"], 0),
            "toneladas_disponibles": round(d["ton"], 0),
            "ritmo_bcm_h": ritmo,
            "autonomia_h": round(autonomia, 1),
            "autonomia_dias": round(autonomia / 24, 1),
            "estado": "ALERTA" if autonomia < AUTONOMIA_CRITICA_H else "OK",
        })
    return filas


def analizar_ciclos(ciclos):
    """Tiempo de ciclo promedio y productividad por pala."""
    acum = defaultdict(lambda: {
        "n": 0, "ton": 0.0, "t_total": 0.0,
        "t_carga": 0.0, "t_viaje": 0.0, "t_cola": 0.0,
    })

    for c in ciclos:
        pala = c["pala"]
        t_ciclo = (float(c["t_carga_min"]) + float(c["t_viaje_min"])
                   + float(c["t_descarga_min"]) + float(c["t_retorno_min"])
                   + float(c["t_cola_min"]))
        a = acum[pala]
        a["n"] += 1
        a["ton"] += float(c["toneladas"])
        a["t_total"] += t_ciclo
        a["t_carga"] += float(c["t_carga_min"])
        a["t_viaje"] += float(c["t_viaje_min"])
        a["t_cola"] += float(c["t_cola_min"])

    filas = []
    for pala in sorted(acum):
        a = acum[pala]
        n = a["n"]
        ciclo_prom = a["t_total"] / n
        filas.append({
            "pala": pala,
            "ciclos": n,
            "toneladas_movidas": round(a["ton"], 0),
            "t_ciclo_prom_min": round(ciclo_prom, 2),
            "t_carga_prom_min": round(a["t_carga"] / n, 2),
            "t_viaje_prom_min": round(a["t_viaje"] / n, 2),
            "t_cola_prom_min": round(a["t_cola"] / n, 2),
            "pct_cola": round(a["t_cola"] / a["t_total"] * 100, 1),
            "ton_por_hora": round(a["ton"] / (a["t_total"] / 60), 0),
        })
    return filas


def priorizar_frentes(frentes, top=10):
    """
    Prioriza frentes disponibles. El indice favorece volumen alto y
    distancia de acarreo corta, que es el criterio operativo habitual
    cuando se define que frentes atacar en el turno.
    """
    activos = [f for f in frentes if f["disponible"] == "SI"]
    if not activos:
        return []

    bcm_max = max(float(f["bcm_disponible"]) for f in activos)
    dist_max = max(float(f["distancia_m"]) for f in activos)

    filas = []
    for f in activos:
        bcm = float(f["bcm_disponible"])
        dist = float(f["distancia_m"])
        score_vol = bcm / bcm_max
        score_dist = 1 - (dist / dist_max)
        indice = 0.6 * score_vol + 0.4 * score_dist
        filas.append({
            "frente_id": f["frente_id"],
            "pit": f["pit"],
            "banco_msnm": f["banco_msnm"],
            "material": f["material"],
            "pala_asignada": f["pala_asignada"],
            "bcm_disponible": int(bcm),
            "distancia_m": int(dist),
            "pendiente_pct": f["pendiente_pct"],
            "indice_prioridad": round(indice, 3),
        })

    filas.sort(key=lambda r: r["indice_prioridad"], reverse=True)
    return filas[:top]


def cumplimiento_turno(ciclos):
    """Produccion por turno frente a la meta, con la desviacion resultante."""
    real = defaultdict(float)
    for c in ciclos:
        real[c["turno"]] += float(c["toneladas"])

    filas = []
    for turno in sorted(real):
        meta = META_TURNO_T.get(turno, 0)
        producido = real[turno]
        desv = producido - meta
        filas.append({
            "turno": turno,
            "meta_t": meta,
            "producido_t": round(producido, 0),
            "desviacion_t": round(desv, 0),
            "cumplimiento_pct": round(producido / meta * 100, 1) if meta else 0,
        })
    return filas


def escribir(nombre, filas):
    if not filas:
        return
    ruta = SALIDAS / nombre
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"  -> salidas/{nombre}")


def tabla(titulo, filas, columnas):
    print()
    print(titulo)
    print("-" * len(titulo))
    anchos = [max(len(str(c)), max((len(str(f[c])) for f in filas), default=0))
              for c in columnas]
    print("  ".join(str(c).ljust(a) for c, a in zip(columnas, anchos)))
    for f in filas:
        print("  ".join(str(f[c]).ljust(a) for c, a in zip(columnas, anchos)))


def main():
    frentes = leer_csv(DATOS / "frentes.csv")
    ciclos = leer_csv(DATOS / "ciclos.csv")

    sv = calcular_shovel_volume(frentes)
    prod = analizar_ciclos(ciclos)
    prio = priorizar_frentes(frentes)
    cump = cumplimiento_turno(ciclos)

    tabla("SHOVEL VOLUME POR PALA", sv,
          ["pala", "frentes_disponibles", "bcm_disponible",
           "toneladas_disponibles", "autonomia_h", "autonomia_dias", "estado"])

    tabla("PRODUCTIVIDAD Y TIEMPOS DE CICLO", prod,
          ["pala", "ciclos", "toneladas_movidas", "t_ciclo_prom_min",
           "t_cola_prom_min", "pct_cola", "ton_por_hora"])

    tabla("PRIORIZACION DE FRENTES (TOP 10)", prio,
          ["frente_id", "pit", "material", "pala_asignada",
           "bcm_disponible", "distancia_m", "indice_prioridad"])

    tabla("CUMPLIMIENTO POR TURNO", cump,
          ["turno", "meta_t", "producido_t", "desviacion_t", "cumplimiento_pct"])

    print()
    print("Archivos generados:")
    escribir("shovel_volume.csv", sv)
    escribir("productividad_palas.csv", prod)
    escribir("frentes_prioritarios.csv", prio)
    escribir("cumplimiento_turno.csv", cump)

    alertas = [f["pala"] for f in sv if f["estado"] == "ALERTA"]
    print()
    if alertas:
        print(f"ALERTA: {', '.join(alertas)} por debajo de "
              f"{AUTONOMIA_CRITICA_H} h de autonomia.")
    else:
        print("Todas las palas por encima del umbral de autonomia.")


if __name__ == "__main__":
    main()
