"""
Generador del modelo de actividades de una operacion a cielo abierto.

IMPORTANTE: nomenclatura y valores completamente ficticios, generados
aleatoriamente. No corresponden a ninguna operacion real.

Estructura del modelo:
    PIT -> FASE -> BLOCK -> BANCO -> HORIZONTE

Cada combinacion produce una actividad minable. Se agregan ademas las
actividades de construccion de acceso (rampa) por pit y banco, porque
ningun banco puede minarse antes de tener via de acceso construida.

Salida:
    datos/actividades.csv

Uso:
    python src/generar_modelo.py
"""

import csv
import random
from pathlib import Path

random.seed(11)

BASE = Path(__file__).resolve().parent.parent
DATOS = BASE / "datos"
DATOS.mkdir(exist_ok=True)

PITS = ["PIT-NORTE", "PIT-CENTRO", "PIT-SUR"]
FASES = [1, 2]
BLOCKS = ["A", "B", "C", "D"]
BANCOS = [1040, 1025, 1010, 995, 980]   # cota, de arriba hacia abajo
HORIZONTES = ["ROCA", "CARBON"]

DENSIDAD = {"ROCA": 2.45, "CARBON": 1.35}
RITMO_BCM_DIA = 14_000   # ritmo de referencia para estimar duraciones


def generar():
    filas = []

    # --- Actividades de acceso: una rampa por pit y banco ---
    for pit in PITS:
        for i, banco in enumerate(BANCOS):
            filas.append({
                "actividad_id": f"{pit}|RAMPA|{banco}",
                "tipo": "ACCESO",
                "pit": pit,
                "fase": 0,
                "block": "-",
                "banco": banco,
                "nivel": i,                 # 0 = banco superior
                "horizonte": "-",
                "strip": 0,
                "distancia_hw_m": 0,
                "volumen_bcm": 0,
                "toneladas": 0,
                "duracion_dias": random.randint(3, 7),
            })

    # --- Actividades minables ---
    for pit in PITS:
        for fase in FASES:
            for j, block in enumerate(BLOCKS):
                # La distancia al techo (hangingwall) crece con el indice del block:
                # define el orden de avance dentro del banco.
                distancia_hw = 120 + j * 165
                for i, banco in enumerate(BANCOS):
                    for horizonte in HORIZONTES:
                        if horizonte == "ROCA":
                            bcm = round(random.uniform(38_000, 96_000), 0)
                        else:
                            bcm = round(random.uniform(6_000, 21_000), 0)
                        ton = bcm * DENSIDAD[horizonte]
                        filas.append({
                            "actividad_id": f"{pit}|F{fase}|{block}|{banco}|{horizonte}",
                            "tipo": "MINADO",
                            "pit": pit,
                            "fase": fase,
                            "block": block,
                            "banco": banco,
                            "nivel": i,
                            "horizonte": horizonte,
                            "strip": j,
                            "distancia_hw_m": distancia_hw,
                            "volumen_bcm": int(bcm),
                            "toneladas": round(ton, 0),
                            "duracion_dias": max(1, round(bcm / RITMO_BCM_DIA)),
                        })
    return filas


if __name__ == "__main__":
    filas = generar()
    ruta = DATOS / "actividades.csv"
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)

    minado = [f for f in filas if f["tipo"] == "MINADO"]
    acceso = [f for f in filas if f["tipo"] == "ACCESO"]
    print(f"actividades.csv: {len(filas)} actividades "
          f"({len(minado)} de minado, {len(acceso)} de acceso)")
    print(f"Volumen total: {sum(f['volumen_bcm'] for f in filas):,.0f} BCM")
