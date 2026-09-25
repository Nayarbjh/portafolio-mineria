"""
Generador de datos sintéticos de operación minera a cielo abierto.

IMPORTANTE: todos los datos producidos por este script son ficticios y generados
aleatoriamente. No corresponden a ninguna operación real.

Genera dos archivos:
  - datos/frentes.csv    : inventario de frentes de trabajo por pit y banco
  - datos/ciclos.csv     : registro de ciclos de acarreo camión-pala

Uso:
    python src/generar_datos.py
"""

import csv
import random
from pathlib import Path

random.seed(2026)

BASE = Path(__file__).resolve().parent.parent
DATOS = BASE / "datos"
DATOS.mkdir(exist_ok=True)

PITS = ["PIT-NORTE", "PIT-CENTRO", "PIT-SUR"]
PALAS = ["SH-01", "SH-02", "SH-03", "SH-04"]
MATERIALES = ["ESTERIL", "CARBON"]

# Densidades in-situ de referencia (t/m3). Valores tipicos de literatura,
# no corresponden a ningun yacimiento en particular.
DENSIDAD = {"ESTERIL": 2.45, "CARBON": 1.35}

# Factor de esponjamiento (swell): volumen suelto / volumen in-situ
ESPONJAMIENTO = {"ESTERIL": 1.30, "CARBON": 1.20}


def generar_frentes(n=24):
    """Inventario de frentes disponibles con su volumen in-situ remanente."""
    filas = []
    for i in range(1, n + 1):
        pit = random.choice(PITS)
        banco = random.choice([1040, 1025, 1010, 995, 980])
        material = random.choices(MATERIALES, weights=[0.78, 0.22])[0]
        # Volumen in-situ disponible en el frente, en BCM (Bank Cubic Meters)
        bcm = round(random.uniform(18_000, 145_000), 0)
        pala = random.choice(PALAS)
        # Distancia one-way del frente al destino, en metros
        distancia_m = round(random.uniform(900, 4_800), 0)
        # Pendiente promedio de la ruta, en porcentaje
        pendiente_pct = round(random.uniform(-8.0, 9.5), 1)
        disponible = random.choices(["SI", "NO"], weights=[0.85, 0.15])[0]
        filas.append({
            "frente_id": f"F-{i:03d}",
            "pit": pit,
            "banco_msnm": banco,
            "material": material,
            "bcm_disponible": int(bcm),
            "pala_asignada": pala,
            "distancia_m": int(distancia_m),
            "pendiente_pct": pendiente_pct,
            "disponible": disponible,
        })
    return filas


def generar_ciclos(frentes, n=900):
    """Registro de ciclos de acarreo. Un ciclo = carga, viaje, descarga, retorno."""
    activos = [f for f in frentes if f["disponible"] == "SI"]
    filas = []
    for i in range(1, n + 1):
        f = random.choice(activos)
        # Capacidad nominal del camion segun material, en toneladas
        cap_t = 218 if f["material"] == "ESTERIL" else 190
        # Factor de llenado real del balde
        factor_llenado = random.uniform(0.86, 1.04)
        toneladas = round(cap_t * factor_llenado, 1)

        # Tiempos del ciclo en minutos
        t_carga = round(random.uniform(2.1, 4.6), 2)
        # La velocidad cargado cae con la pendiente positiva
        vel_cargado = max(12.0, 26.0 - f["pendiente_pct"] * 0.9)
        t_viaje = round((f["distancia_m"] / 1000) / vel_cargado * 60, 2)
        t_descarga = round(random.uniform(0.8, 1.9), 2)
        t_retorno = round((f["distancia_m"] / 1000) / 32.0 * 60, 2)
        t_cola = round(max(0.0, random.gauss(3.2, 2.4)), 2)

        filas.append({
            "ciclo_id": f"C-{i:05d}",
            "turno": random.choice(["DIA", "NOCHE"]),
            "frente_id": f["frente_id"],
            "pala": f["pala_asignada"],
            "material": f["material"],
            "toneladas": toneladas,
            "t_carga_min": t_carga,
            "t_viaje_min": t_viaje,
            "t_descarga_min": t_descarga,
            "t_retorno_min": t_retorno,
            "t_cola_min": t_cola,
        })
    return filas


def escribir(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"  {ruta.name}: {len(filas)} registros")


if __name__ == "__main__":
    print("Generando datos sinteticos...")
    frentes = generar_frentes()
    ciclos = generar_ciclos(frentes)
    escribir(DATOS / "frentes.csv", frentes)
    escribir(DATOS / "ciclos.csv", ciclos)
    print("Listo.")
