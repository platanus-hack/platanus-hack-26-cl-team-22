# Modelo de hogares

Estado al 21 de noviembre de 2026. Mecanismo 2 del modelo (ver
[`contexto-proyecto.md`](./contexto-proyecto.md), sección 4). Código en `core/hogares.py`;
calibración en `experiments/calibrar_hogares.py`; resultados en
`results/hogares_calibracion.json`. Datos: matrices del censo en `data/censo/` (Massiel).

Reproducir:

```
python -m experiments.calibrar_hogares
```

## Ecuaciones

Cada año, para cada comuna `i`:

```
salen[i]     = población[i] · r[i]
flujo[i, j]  = salen[i] · s[i, j]                 (j ≠ i)
población'   = población − salen + llegan        (con tope de viviendas opcional)
```

| Símbolo | Qué es | Origen |
|---|---|---|
| `r[i]` | Tasa anual de salida: la **inercia** | Matriz 2012→2017: `R5 = (fila − diagonal) / fila`, anualizada con `r = 1 − (1 − R5)^(1/5)` (riesgo constante, supuesto) |
| `s[i, j]` | A dónde van quienes salen de `i` | Proporciones observadas en la fila `i` de la matriz 2012→2017 |
| Tope | Capacidad de vivienda por comuna | Opcional. Si una comuna se llena, quienes no caben se quedan en su comuna de origen |

La población total de la región se conserva exactamente (hay un test). El sistema es cerrado:
no hay nacimientos, muertes ni mudanzas desde o hacia fuera de la RM (las matrices no las
traen; ver `data/censo/README.md`).

## Qué no hace, y por qué

**El aire no cambia a dónde se muda la gente.** Se podría estimar un término de aire con un
modelo de elección de destino, pero con un solo corte del censo el resultado no sería
preferencia por aire limpio: en la RM el aire peor (poniente) y el crecimiento (periferia)
siguen al ingreso y al precio de la vivienda. Cualquier signo que saliera sería confusión.
Queda en 0 y se dice.

El acople con el aire va en la otra dirección: **la gente que se muda cambia las emisiones de
leña** (ver abajo).

## Ajuste y prueba

Se ajusta con 2012→2017 y se prueba con 2019→2024. Métrica: migración neta por comuna (llegan
menos salen) en los 5 años.

| Prueba | Modelo | Nadie se muda | Repetir 2012→2017 |
|---|---|---|---|
| En la muestra (2012→2017), RMSE | 755 personas (correlación 0,993) | — | — |
| **Fuera de la muestra (2019→2024), RMSE** | **4.335** | 7.716 | 5.054 |
| Fuera de la muestra, correlación | **0,83** | — | 0,76 |
| Fuera de la muestra, error absoluto medio | 3.013 | 5.252 | 3.012 |

- La inercia es estable: la tasa de salida por comuna se correlaciona 0,95 entre los dos
  períodos (mediana anual 3,1 % contra 2,7 %).
- El modelo le gana a «nadie se muda» y a «repetir lo de 2012→2017» en error cuadrático y en
  correlación. En error absoluto medio empata con repetir: la ventaja es modesta.
- **Mayores errores**: Ñuñoa (ganó 17.301; el modelo esperaba 1.480), Providencia, Las Condes,
  Maipú y Puente Alto. El error se correlaciona 0,36 con las viviendas nuevas 2017→2024 (Ñuñoa
  sumó 32 %). No se agregó un término de vivienda: las viviendas de 2024 son parte del período
  de prueba y usarlas sería ajustar con los datos con que se prueba.
- **2019→2024 incluye el estallido y la pandemia.** Santiago perdió 30 mil personas aunque sumó
  24 % de viviendas; parte del error es del período, no del modelo.

## El acople con el aire

El RETC estima la leña residencial de arriba hacia abajo: viviendas × fracción que usa leña ×
consumo por vivienda × factor de emisión, con la CASEN y proyecciones de población
([Reporte RETC 2005–2017](https://retc.mma.gob.cl/wp-content/uploads/2021/07/Reporte-RETC-2005-2017.pdf),
[inventario residencial RM 2023](https://airerm.mma.gob.cl/wp-content/uploads/2024/03/2023_Inventario-Residencial.pdf)).
Por eso escalar la leña de una comuna con su población es coherente con el dato (aunque
circular). Lo que no sabemos es si quien llega a una vivienda nueva en Lampa quema leña:
el art. 75 del PPDA solo permite calefactores nuevos certificados en la Zona B.

Dos lecturas, y se publican las dos:

| Lectura | Supuesto | Qué representa |
|---|---|---|
| `proporcional` | La leña de cada comuna crece o baja con su población | Cota superior del efecto |
| `fija` | La leña no cambia con la población | Cota inferior: sin acople |

Transporte, industria y otras no se escalan: el transporte del RETC no se asigna por lugar de
residencia, y la industria y los incendios no siguen a los residentes.

## En la simulación 2026–2036

`make simulate` parte de la población del censo 2024 y aplica las mudanzas cada año, con los
parámetros 2012→2017 (los validados). El tope de viviendas crece al ritmo de las viviendas de
cada comuna entre 2017 y 2024; no se alcanza en ninguna comuna.

- **La ciudad se muda hacia la Zona B**: pasa de 1.140.547 a 1.350.891 habitantes en 2036
  (+18 %), sobre todo en Lampa, Colina y Buin.
- La población de cada comuna se publica como la variable `crecimiento_poblacion` (% desde
  2024). No tiene banda: las mudanzas son flujos esperados, no se sortean.

PM2,5 en 2036, promedio ponderado por la población de 2036 (nivel 2023: 23,1 µg/m³, con las
comunas con estación ancladas a su medición):

| Escenario | Leña fija | Leña sigue a la gente |
|---|---|---|
| Ninguna política avanza | 22,9 | **24,4** |
| Planes vigentes, cumplimiento real | 21,4 (20,2–22,4) | **22,9** (21,7–23,9) |
| Planes vigentes + prohibición en la Zona B | 18,5 (15,6–21,1) | 19,5 (16,1–22,4) |

Qué significa:

- **Si la leña sigue a la gente, la migración a la Zona B compensa la mejora del plan.** El
  plan rinde lo mismo en ambas lecturas (unos −1,5 µg/m³), pero la migración agrega unos
  +1,5: sin políticas la región pasaría de 22,9 a 24,4, y con el plan vigente queda en 22,9,
  prácticamente el nivel de hoy (23,1). Es la cota superior; con la leña fija queda en 21,4.
- **La prohibición en la Zona B vale más cuanta más gente se muda allí**: mediana de la
  diferencia pareada por réplica (con y sin la prohibición, misma semilla) de −3,9 µg/m³ con
  la leña siguiendo a la gente contra −3,2 con la leña fija (19 % más), porque también cubre
  la leña de quienes llegan. Es una interacción entre dos mecanismos, no una suma. La banda
  es ancha: entre −1,0 y −5,8 (p10 a p90) en la lectura proporcional.

### Qué no hace todavía

- **El lazo no está cerrado.** Hay una cadena en un sentido (mudanzas → leña → aire) y una
  interacción con las políticas, pero el aire no cambia a dónde se muda la gente (término de
  aire en 0, ver arriba). Los destinos repiten las proporciones observadas.
- Por lo mismo, `crecimiento_poblacion` es igual en todos los escenarios: los pesos
  reordenan comunas, pero ningún interruptor de políticas cambia esa variable.
- El tope de viviendas no se alcanza: la población regional es fija y las viviendas crecen.
- Los interruptores de la interfaz usan la lectura `fija` (no exagera). Los tres escenarios
  `…-lena-sigue-a-la-gente` muestran la cota superior. Cambiar la lectura por defecto es una
  constante en `experiments/simular.py` (`DEFAULT_HOUSEHOLDS`).

## Siguientes versiones

1. Vivienda nueva como atractor, ajustada con 2012→2017 y probada con 2019→2024 (hoy no hay
   viviendas de 2012 para hacerlo sin filtrar datos de prueba).
2. Flujo externo: llegadas desde otras regiones y del extranjero, y crecimiento natural.
3. Aire como motivo de mudanza, solo si aparece una fuente que permita identificarlo.
