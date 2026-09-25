"""
Motor de reglas de dependencia automatica y validacion del grafo de secuencia.

Reproduce, sobre un modelo ficticio, la logica que un motor de dependencias
automaticas aplica en un software de planeacion (Deswik.Sched y equivalentes):
a partir de los atributos de cada actividad, genera las relaciones de
precedencia sin tener que enlazarlas manualmente una por una.

Reglas implementadas
--------------------
R1  ACCESO_VERTICAL       la rampa de un banco requiere la rampa del banco superior
R2  ACCESO_A_MINADO       minar un banco requiere su rampa construida
R3  BANCO_DESCENDENTE     un banco no se mina antes que el banco inmediatamente superior
R4  HORIZONTE             dentro de un banco, el esteril precede al carbon
R5  AVANCE_HW_LW          dentro de un banco, el avance va del techo hacia el piso
R6  SECUENCIA_FASES       una fase posterior arranca cuando la anterior ha avanzado

Tipos de relacion
-----------------
FS  Finish-to-Start   la sucesora empieza cuando termina la predecesora
SS  Start-to-Start    la sucesora empieza cuando la predecesora lleva N dias

Validaciones
------------
- Deteccion de ciclos (una dependencia circular bloquea el programa completo)
- Actividades huerfanas (sin predecesora y sin ser un arranque legitimo)
- Actividades inalcanzables desde los arranques del programa
- Programacion por fechas tempranas y ruta critica

Uso:
    python src/generar_modelo.py
    python src/reglas_dependencia.py
"""

import csv
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent
DATOS = BASE / "datos"
SALIDAS = BASE / "salidas"
SALIDAS.mkdir(exist_ok=True)

# Desfase entre fases consecutivas del mismo pit, en dias
LAG_FASES_DIAS = 45

# Traslape permitido en el avance techo-piso dentro de un banco, en dias
LAG_AVANCE_DIAS = 10


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------

def cargar_actividades():
    with open(DATOS / "actividades.csv", encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    for f in filas:
        f["fase"] = int(f["fase"])
        f["banco"] = int(f["banco"])
        f["nivel"] = int(f["nivel"])
        f["strip"] = int(f["strip"])
        f["duracion_dias"] = int(f["duracion_dias"])
        f["volumen_bcm"] = int(f["volumen_bcm"])
    return filas


def indexar(actividades):
    return {a["actividad_id"]: a for a in actividades}


# --------------------------------------------------------------------------
# Reglas
# --------------------------------------------------------------------------

def r1_acceso_vertical(acts):
    """La rampa de un banco requiere la del banco inmediatamente superior."""
    deps = []
    rampas = defaultdict(list)
    for a in acts:
        if a["tipo"] == "ACCESO":
            rampas[a["pit"]].append(a)
    for pit, lista in rampas.items():
        lista.sort(key=lambda x: x["nivel"])
        for prev, cur in zip(lista, lista[1:]):
            deps.append((prev["actividad_id"], cur["actividad_id"],
                          "FS", 0, "R1_ACCESO_VERTICAL"))
    return deps


def r2_acceso_a_minado(acts):
    """Ninguna actividad de minado arranca sin la rampa de su banco."""
    deps = []
    rampa_de = {}
    for a in acts:
        if a["tipo"] == "ACCESO":
            rampa_de[(a["pit"], a["banco"])] = a["actividad_id"]
    for a in acts:
        if a["tipo"] != "MINADO" or a["horizonte"] != "ROCA":
            continue
        clave = (a["pit"], a["banco"])
        if clave in rampa_de:
            deps.append((rampa_de[clave], a["actividad_id"],
                          "FS", 0, "R2_ACCESO_A_MINADO"))
    return deps


def r3_banco_descendente(acts):
    """
    Un banco no puede minarse antes que el banco inmediatamente superior
    del mismo block. Es la restriccion geometrica basica del cielo abierto.
    Se enlaza el ultimo horizonte del banco superior con el primero del inferior.
    """
    deps = []
    por_block = defaultdict(list)
    for a in acts:
        if a["tipo"] == "MINADO":
            por_block[(a["pit"], a["fase"], a["block"])].append(a)

    for _, lista in por_block.items():
        niveles = defaultdict(list)
        for a in lista:
            niveles[a["nivel"]].append(a)
        for nivel in sorted(niveles)[:-1]:
            arriba = niveles[nivel]
            abajo = niveles.get(nivel + 1, [])
            if not abajo:
                continue
            fin_arriba = next((x for x in arriba if x["horizonte"] == "CARBON"), arriba[-1])
            ini_abajo = next((x for x in abajo if x["horizonte"] == "ROCA"), abajo[0])
            deps.append((fin_arriba["actividad_id"], ini_abajo["actividad_id"],
                          "FS", 0, "R3_BANCO_DESCENDENTE"))
    return deps


def r4_horizonte(acts):
    """Dentro de un banco, el esteril se remueve antes de extraer el carbon."""
    deps = []
    por_banco = defaultdict(dict)
    for a in acts:
        if a["tipo"] == "MINADO":
            por_banco[(a["pit"], a["fase"], a["block"], a["banco"])][a["horizonte"]] = a
    for _, h in por_banco.items():
        if "ROCA" in h and "CARBON" in h:
            deps.append((h["ROCA"]["actividad_id"], h["CARBON"]["actividad_id"],
                          "FS", 0, "R4_HORIZONTE"))
    return deps


def r5_avance_hw_lw(acts):
    """
    El avance dentro de un banco va del techo hacia el piso, siguiendo el
    orden de distancia al hangingwall. Se modela como SS con desfase, porque
    los blocks contiguos pueden traslaparse parcialmente.
    """
    deps = []
    por_banco = defaultdict(list)
    for a in acts:
        if a["tipo"] == "MINADO" and a["horizonte"] == "ROCA":
            por_banco[(a["pit"], a["fase"], a["banco"])].append(a)
    for _, lista in por_banco.items():
        lista.sort(key=lambda x: x["strip"])
        for prev, cur in zip(lista, lista[1:]):
            deps.append((prev["actividad_id"], cur["actividad_id"],
                          "SS", LAG_AVANCE_DIAS, "R5_AVANCE_HW_LW"))
    return deps


def r6_secuencia_fases(acts):
    """
    Una fase posterior no arranca hasta que la anterior lleva un avance
    determinado en el mismo block y banco. Evita que dos fases del mismo
    pit compitan por el mismo espacio operativo.
    """
    deps = []
    idx = {}
    for a in acts:
        if a["tipo"] == "MINADO" and a["horizonte"] == "ROCA":
            idx[(a["pit"], a["fase"], a["block"], a["banco"])] = a
    for (pit, fase, block, banco), a in idx.items():
        anterior = idx.get((pit, fase - 1, block, banco))
        if anterior:
            deps.append((anterior["actividad_id"], a["actividad_id"],
                          "SS", LAG_FASES_DIAS, "R6_SECUENCIA_FASES"))
    return deps


REGLAS = [
    ("R1_ACCESO_VERTICAL", r1_acceso_vertical),
    ("R2_ACCESO_A_MINADO", r2_acceso_a_minado),
    ("R3_BANCO_DESCENDENTE", r3_banco_descendente),
    ("R4_HORIZONTE", r4_horizonte),
    ("R5_AVANCE_HW_LW", r5_avance_hw_lw),
    ("R6_SECUENCIA_FASES", r6_secuencia_fases),
]


def aplicar_reglas(acts):
    todas, resumen = [], []
    for nombre, fn in REGLAS:
        generadas = fn(acts)
        todas.extend(generadas)
        resumen.append({"regla": nombre, "dependencias": len(generadas)})
    # Elimina duplicados exactos conservando el orden de aplicacion
    vistas, unicas = set(), []
    for d in todas:
        clave = (d[0], d[1])
        if clave not in vistas:
            vistas.add(clave)
            unicas.append(d)
    return unicas, resumen


# --------------------------------------------------------------------------
# Validacion del grafo
# --------------------------------------------------------------------------

def construir_grafo(deps):
    sucesores = defaultdict(list)
    predecesores = defaultdict(list)
    for pred, suc, tipo, lag, regla in deps:
        sucesores[pred].append((suc, tipo, lag))
        predecesores[suc].append((pred, tipo, lag))
    return sucesores, predecesores


def detectar_ciclos(nodos, sucesores):
    """DFS con marcado de tres colores. Devuelve el primer ciclo encontrado."""
    BLANCO, GRIS, NEGRO = 0, 1, 2
    color = {n: BLANCO for n in nodos}
    ciclos = []

    def visitar(n, camino):
        color[n] = GRIS
        camino.append(n)
        for suc, _, _ in sucesores.get(n, []):
            if color.get(suc, BLANCO) == GRIS:
                ciclos.append(camino[camino.index(suc):] + [suc])
            elif color.get(suc, BLANCO) == BLANCO:
                visitar(suc, camino)
        camino.pop()
        color[n] = NEGRO

    for n in nodos:
        if color[n] == BLANCO:
            visitar(n, [])
    return ciclos


def detectar_huerfanas(acts, predecesores):
    """
    Actividad sin predecesora que no es un arranque legitimo del programa.
    Arranque legitimo = rampa del banco superior de cada pit.
    """
    legitimas = set()
    for a in acts:
        if a["tipo"] == "ACCESO" and a["nivel"] == 0:
            legitimas.add(a["actividad_id"])

    huerfanas = []
    for a in acts:
        aid = a["actividad_id"]
        if not predecesores.get(aid) and aid not in legitimas:
            huerfanas.append(aid)
    return huerfanas, sorted(legitimas)


def programar(acts, deps, idx):
    """
    Pase hacia adelante: fecha de inicio mas temprana de cada actividad
    respetando el tipo de relacion y el desfase. Devuelve tambien la
    actividad de mayor fecha de terminacion, que marca la duracion del programa.
    """
    sucesores, predecesores = construir_grafo(deps)
    nodos = [a["actividad_id"] for a in acts]

    # Orden topologico por conteo de grados de entrada (Kahn)
    grado = {n: len(predecesores.get(n, [])) for n in nodos}
    cola = [n for n in nodos if grado[n] == 0]
    orden = []
    while cola:
        n = cola.pop(0)
        orden.append(n)
        for suc, _, _ in sucesores.get(n, []):
            grado[suc] -= 1
            if grado[suc] == 0:
                cola.append(suc)

    if len(orden) != len(nodos):
        return None, None, None   # hay ciclo, no se puede programar

    inicio = {n: 0 for n in nodos}
    fin = {n: 0 for n in nodos}
    origen = {n: None for n in nodos}

    for n in orden:
        dur = idx[n]["duracion_dias"]
        es = 0
        src = None
        for pred, tipo, lag in predecesores.get(n, []):
            cand = fin[pred] + lag if tipo == "FS" else inicio[pred] + lag
            if cand > es:
                es, src = cand, pred
        inicio[n], fin[n], origen[n] = es, es + dur, src

    return inicio, fin, origen


def ruta_critica(fin, origen):
    ultimo = max(fin, key=lambda n: fin[n])
    cadena, n = [], ultimo
    while n is not None:
        cadena.append(n)
        n = origen[n]
    return list(reversed(cadena)), fin[ultimo]


# --------------------------------------------------------------------------
# Salida
# --------------------------------------------------------------------------

def escribir(nombre, filas):
    if not filas:
        return
    with open(SALIDAS / nombre, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"  -> salidas/{nombre}")


def main():
    acts = cargar_actividades()
    idx = indexar(acts)

    print(f"Modelo: {len(acts)} actividades")
    print()

    deps, resumen = aplicar_reglas(acts)
    print("DEPENDENCIAS GENERADAS POR REGLA")
    print("-" * 34)
    for r in resumen:
        print(f"{r['regla']:<24} {r['dependencias']:>5}")
    print(f"{'TOTAL (sin duplicados)':<24} {len(deps):>5}")

    sucesores, predecesores = construir_grafo(deps)
    nodos = [a["actividad_id"] for a in acts]

    print()
    print("VALIDACION DEL GRAFO")
    print("-" * 20)

    ciclos = detectar_ciclos(nodos, sucesores)
    if ciclos:
        print(f"CICLOS DETECTADOS: {len(ciclos)}")
        for c in ciclos[:3]:
            print("   " + " -> ".join(c))
    else:
        print("Ciclos: ninguno. El grafo es aciclico y se puede programar.")

    huerfanas, arranques = detectar_huerfanas(acts, predecesores)
    print(f"Arranques del programa: {len(arranques)}")
    if huerfanas:
        print(f"HUERFANAS: {len(huerfanas)} actividades sin predecesora")
        for h in huerfanas[:5]:
            print(f"   {h}")
    else:
        print("Huerfanas: ninguna. Toda actividad cuelga de un arranque valido.")

    sin_sucesor = [n for n in nodos if not sucesores.get(n)]
    print(f"Actividades terminales: {len(sin_sucesor)}")

    inicio, fin, origen = programar(acts, deps, idx)
    if inicio is None:
        print()
        print("No se pudo programar: el grafo contiene ciclos.")
        return

    cadena, duracion = ruta_critica(fin, origen)
    print()
    print("PROGRAMACION POR FECHAS TEMPRANAS")
    print("-" * 33)
    print(f"Duracion del programa: {duracion} dias ({duracion/365:.1f} anos)")
    print(f"Actividades en ruta critica: {len(cadena)}")
    print()
    print("Primeros ocho eslabones de la ruta critica:")
    for n in cadena[:8]:
        a = idx[n]
        print(f"   dia {inicio[n]:>5}  {n:<38} {a['duracion_dias']:>3} d")

    print()
    print("Archivos generados:")
    escribir("dependencias.csv", [
        {"predecesora": p, "sucesora": s, "tipo": t, "lag_dias": l, "regla": r}
        for p, s, t, l, r in deps
    ])
    escribir("resumen_reglas.csv", resumen)
    escribir("programa.csv", [
        {
            "actividad_id": n,
            "tipo": idx[n]["tipo"],
            "pit": idx[n]["pit"],
            "fase": idx[n]["fase"],
            "banco": idx[n]["banco"],
            "horizonte": idx[n]["horizonte"],
            "volumen_bcm": idx[n]["volumen_bcm"],
            "inicio_dia": inicio[n],
            "fin_dia": fin[n],
            "en_ruta_critica": "SI" if n in set(cadena) else "NO",
        }
        for n in sorted(nodos, key=lambda x: inicio[x])
    ])


if __name__ == "__main__":
    main()
