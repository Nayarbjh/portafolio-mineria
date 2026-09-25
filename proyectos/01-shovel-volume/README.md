# Shovel Volume y priorización de frentes

Cálculo del volumen de roca disponible por pala y priorización de frentes de trabajo
en una operación de minería a cielo abierto, reproduciendo el análisis que sustenta
la reunión diaria de prioridades con el departamento de Producción.

> **Nota sobre los datos.** Todos los datos de este repositorio son sintéticos y se
> generan aleatoriamente con `src/generar_datos.py`. No provienen de ninguna operación
> real ni contienen información de ninguna compañía.

---

## Qué resuelve

En planeación de corto plazo, la pregunta diaria es sencilla de enunciar y difícil de
responder bien: **¿cuánto material tiene disponible cada pala, y por dónde conviene
atacar en el turno?** De esa respuesta dependen la asignación de frentes, la
distribución de la flota de acarreo y el cumplimiento de la meta de producción.

Este proyecto automatiza ese cálculo y entrega cuatro salidas:

| Salida | Contenido |
|---|---|
| `shovel_volume.csv` | BCM, LCM y toneladas disponibles por pala, con autonomía en horas y días |
| `productividad_palas.csv` | Tiempo de ciclo promedio, descomposición del ciclo y t/h por pala |
| `frentes_prioritarios.csv` | Ranking de frentes según volumen disponible y distancia de acarreo |
| `cumplimiento_turno.csv` | Producción real contra meta por turno, con la desviación |

---

## Criterio técnico

**Conversión volumétrica.** El inventario de frentes se lleva en BCM (*bank cubic
meters*, volumen in-situ), que es la unidad de planeación. Para estimar la carga real
de la flota se convierte a LCM aplicando el factor de esponjamiento, y a toneladas
aplicando la densidad in-situ del material. Se diferencian estéril y carbón porque
ambos parámetros cambian de forma significativa entre uno y otro.

**Autonomía.** Cada pala se evalúa dividiendo su volumen disponible entre su ritmo
nominal de producción. Por debajo de un umbral configurable (24 h por defecto) la pala
entra en alerta: es la señal de que hay que liberar frente antes de que la operación se
detenga por falta de material expuesto.

**Índice de priorización.** Combina volumen disponible normalizado (60 %) y cercanía al
destino (40 %). El peso hacia el volumen evita fragmentar la operación en frentes
pequeños; el peso hacia la distancia reconoce que el acarreo es el componente dominante
del ciclo y del costo. Los pesos son parámetros, no constantes: se ajustan al criterio
de cada operación.

**Descomposición del ciclo.** El tiempo de ciclo se separa en carga, viaje cargado,
descarga, retorno y cola. El porcentaje en cola es el indicador más útil de los cinco,
porque señala desbalance entre la capacidad de cargue y el número de camiones
asignados, que es corregible dentro del mismo turno.

---

## Cómo ejecutarlo

Solo requiere Python 3.9 o superior. No usa dependencias externas.

```bash
python src/generar_datos.py    # genera datos/frentes.csv y datos/ciclos.csv
python src/shovel_volume.py    # imprime el reporte y escribe salidas/
```

---

## Estructura

```
01-shovel-volume/
├── datos/        CSV de entrada generados sintéticamente
├── src/
│   ├── generar_datos.py    generador de datos sintéticos
│   └── shovel_volume.py    cálculo, priorización y reporte
└── salidas/      CSV de resultados
```

---

## Parámetros configurables

En `src/shovel_volume.py`:

- `DENSIDAD` — densidad in-situ por material (t/m³)
- `ESPONJAMIENTO` — factor volumen suelto / volumen in-situ
- `RITMO_PALA_BCM_H` — ritmo nominal de producción por pala
- `META_TURNO_T` — meta de producción por turno
- `AUTONOMIA_CRITICA_H` — umbral de alerta de autonomía

---

## Próximos pasos

- Simulación de asignación de flota y cálculo del número óptimo de camiones por frente
- Exportación del ranking de frentes a formato compatible con Deswik.Sched
- Tablero de seguimiento en Power BI sobre las salidas del modelo
