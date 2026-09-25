# Reglas de dependencia automática y validación del grafo de secuencia

Generación automática de relaciones de precedencia a partir de los atributos de las
actividades, y validación del grafo resultante antes de programar.

> **Nota sobre los datos.** El modelo, la nomenclatura de pits, fases y bancos, y todos
> los valores son ficticios y se generan aleatoriamente con `src/generar_modelo.py`.
> Las reglas fueron construidas desde primeros principios geométricos y operativos.
> Este proyecto no contiene ni deriva de la configuración de ninguna compañía.

---

## El problema

Un plan de mediano plazo puede tener varios miles de actividades. Enlazarlas a mano es
inviable, y peor: cada vez que cambia el diseño hay que rehacer los enlaces.

Los motores de dependencia automática de los software de planeación (Deswik.Sched y
equivalentes) resuelven esto de otra forma. En lugar de enlazar actividades, se
declaran **reglas** sobre los atributos: *"dentro del mismo block, el banco inferior
depende del superior"*. El motor recorre el modelo y genera los miles de enlaces solo.

El valor está en las reglas, no en los enlaces. Una regla mal planteada produce un
programa que se ve bien en el Gantt y es imposible de ejecutar en terreno.

---

## Las seis reglas

| Regla | Qué impone | Tipo | Razón |
|---|---|---|---|
| **R1** Acceso vertical | La rampa de un banco requiere la del banco superior | FS | No se construye acceso a un nivel al que no se ha llegado |
| **R2** Acceso a minado | Minar un banco requiere su rampa construida | FS | Sin vía no entra flota |
| **R3** Banco descendente | Un banco no se mina antes que el inmediatamente superior | FS | Restricción geométrica básica del cielo abierto |
| **R4** Horizonte | Dentro de un banco, el estéril precede al carbón | FS | El descapote antecede a la extracción |
| **R5** Avance techo-piso | El avance sigue el orden de distancia al hangingwall | SS + 10 d | Dirección natural del avance; admite traslape parcial |
| **R6** Secuencia de fases | Una fase posterior arranca cuando la anterior ha avanzado | SS + 45 d | Evita que dos fases compitan por el mismo espacio operativo |

**Por qué R5 y R6 son SS y no FS.** Una relación *finish-to-start* obliga a terminar por
completo un block antes de empezar el contiguo, lo que serializa la operación y genera
un programa artificialmente largo. En terreno los frentes contiguos se traslapan. El
*start-to-start* con desfase captura eso: el segundo block arranca cuando el primero
lleva el avance suficiente para liberar espacio. El desfase es un parámetro de calibración,
no una constante.

---

## Las validaciones

Generar dependencias es la parte fácil. Lo que separa un plan ejecutable de uno que
falla en la primera corrida es lo que se revisa después.

**Ciclos.** Si A depende de B y B termina dependiendo de A, el programa no se puede
resolver. Con reglas superpuestas sobre miles de actividades, los ciclos aparecen sin
que nadie los haya escrito. Se detectan con recorrido en profundidad y marcado de tres
colores, y el script reporta la cadena completa del ciclo para poder corregir la regla
que lo originó.

**Huérfanas.** Una actividad sin predecesora arranca el día cero. Si eso no era la
intención, aparece minándose material antes de tener acceso, y en un Gantt de miles de
líneas nadie lo nota. El validador distingue entre arranques legítimos del programa
—las rampas del banco superior de cada pit— y actividades que quedaron sueltas por un
error en el filtro de alguna regla.

**Alcanzabilidad.** Toda actividad debe poder alcanzarse desde algún arranque. Un
subgrafo desconectado es una parte del plan que el motor programó sin restricciones.

**Programación y ruta crítica.** Ordenamiento topológico por el algoritmo de Kahn y
pase hacia adelante respetando el tipo de relación y el desfase de cada enlace. La ruta
crítica se reconstruye hacia atrás desde la actividad de mayor fecha de terminación.

---

## Resultado sobre el modelo de ejemplo

```
Modelo: 255 actividades (240 de minado, 15 de acceso)
Volumen total: 9.280.135 BCM

R1_ACCESO_VERTICAL          12
R2_ACCESO_A_MINADO         120
R3_BANCO_DESCENDENTE        96
R4_HORIZONTE               120
R5_AVANCE_HW_LW             90
R6_SECUENCIA_FASES          60
TOTAL (sin duplicados)     498

Ciclos: ninguno. El grafo es aciclico y se puede programar.
Arranques del programa: 3
Huerfanas: ninguna. Toda actividad cuelga de un arranque valido.
```

Seis reglas producen 498 relaciones. Ese es exactamente el argumento a favor del
enfoque: seis declaraciones mantenibles en lugar de 498 enlaces manuales que habría que
rehacer con cada cambio de diseño.

---

## Cómo ejecutarlo

Python 3.9 o superior. Sin dependencias externas.

```bash
python src/generar_modelo.py        # genera datos/actividades.csv
python src/reglas_dependencia.py    # aplica reglas, valida y programa
```

---

## Estructura

```
02-reglas-dependencia/
├── datos/
│   └── actividades.csv         modelo sintético PIT → FASE → BLOCK → BANCO → HORIZONTE
├── src/
│   ├── generar_modelo.py       generador del modelo de actividades
│   └── reglas_dependencia.py   motor de reglas, validador y programador
└── salidas/
    ├── dependencias.csv        las 498 relaciones con su regla de origen
    ├── resumen_reglas.csv      conteo por regla
    └── programa.csv            fechas tempranas y marca de ruta crítica
```

Cada dependencia queda trazada a la regla que la generó. Cuando el programa arroja algo
inesperado, esa columna es lo que permite encontrar la regla responsable en lugar de
revisar enlaces uno por uno.

---

## Limitaciones conocidas

El modelo no tiene restricción de recursos. Programa como si hubiera equipo de cargue
ilimitado, así que la duración resultante es un límite inferior teórico y no un
programa ejecutable. Incorporar nivelación de recursos es el paso siguiente y es el que
más acerca el resultado a la realidad.

Las duraciones se derivan de un ritmo de producción único. Una versión más fina las
haría depender del equipo asignado y del material.

---

## Próximos pasos

- Nivelación de recursos por equipo de cargue y cálculo de la flota requerida
- Reglas de dependencia entre pits para modelar botaderos y destinos compartidos
- Exportación del grafo a formato compatible con software de planeación
- Visualización del Gantt y del grafo de precedencias
