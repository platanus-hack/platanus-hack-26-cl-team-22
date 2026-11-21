# ¿La vivienda nueva explica a dónde se muda la gente?

Estado al 21 de noviembre de 2026. Los errores más grandes del modelo de hogares están en
comunas con mucha vivienda nueva (`docs/modelo-hogares.md`). Este experimento prueba si los
permisos de edificación del MINVU (`data/vivienda/`) mejoran la predicción de a dónde va quien
se muda.

Código: `experiments/validar_vivienda.py`. Resultado: `results/vivienda_validacion.json`.

```
python -m experiments.validar_vivienda
```

## Prueba

Se usa la misma métrica que `experiments/calibrar_hogares.py`: la migración neta por comuna de
2019→2024, partiendo de los orígenes de 2019 y con 5 pasos anuales. Todos los modelos usan la
tasa de salida de 2012–2017; **solo cambia el destino** de quien se muda. Los parámetros y el
rezago de los permisos se eligen solo con la matriz 2012→2017.

| Modelo de destino | Qué supone |
|---|---|
| Proporciones 2012–2017 | Los destinos observados (el modelo en producción) |
| Gravedad | Atrae más una comuna con más viviendas y más cercana |
| Gravedad + permisos | Además atrae la vivienda nueva: permisos de 5 años / viviendas del censo 2017 |
| Pivote por permisos | Proporciones observadas × cambio de la vivienda nueva entre períodos, con la elasticidad de la gravedad + permisos |
| Radiación | Sin parámetros (Simini y otros 2012) |

## Resultado

Rezago elegido en el ajuste: 3 años. La ventana de ajuste es 2009–2013 y la de prueba,
2016–2020. Elasticidad de la vivienda nueva: **g = 2,75**. Es positiva: dentro del ajuste, la
vivienda nueva atrae mudanzas.

| Modelo (fuera de muestra, 2019→2024) | RMSE | Error absoluto medio | Correlación |
|---|---|---|---|
| **Proporciones 2012–2017 (en producción)** | **4.335** | 3.013 | 0,83 |
| Pivote por permisos | 5.050 | 3.039 | **0,84** |
| Pivote, solo permisos conocidos en 2019 (2014–2018) | 5.230 | **2.726** | 0,82 |
| Repetir 2012→2017 | 5.054 | 3.012 | 0,76 |
| Nadie se muda | 7.716 | 5.252 | — |
| Gravedad | 8.100 | 6.252 | 0,29 |
| Gravedad + permisos | 9.572 | 6.636 | 0,41 |
| Radiación | 14.900 | 11.555 | 0,03 |

## Qué significa

1. **Los permisos no mejoran el error cuadrático. El modelo en producción se queda.** El pivote
   mejora un poco la correlación y, con permisos conocidos en 2019, el error absoluto medio,
   pero empeora el RMSE.
2. **La señal existe y tiene el signo correcto.** El pivote corrige la dirección en Ñuñoa: el
   modelo actual espera 1.480, el pivote 26.566 y se observaron 17.301. También acerca Maipú y
   Puente Alto.
3. **Exagera en las comunas centrales con un salto de permisos:**

   | Comuna | Pivote | Observado |
   |---|---|---|
   | Macul | +14.850 | +2.084 |
   | La Cisterna | +20.264 | +4.966 |
   | Estación Central | +5.697 | −5.964 |

4. **La razón: esas viviendas las llenó la inmigración internacional.** Los permisos 2016–2020
   tienen correlación **0,76** por comuna con las llegadas desde el extranjero 2019–2024
   (`data/censo/flujos_externos.csv`). Estación Central sumó 23.539 viviendas, recibió 31.953
   personas desde el extranjero y perdió 5.964 en mudanzas internas. Si los permisos se cargan
   solo sobre los destinos de las mudanzas internas, se les atribuye una demanda que vino de
   afuera.
5. **Los modelos que no usan los destinos observados pierden por mucho**, incluso contra «nadie
   se muda». La estructura observada de destinos pesa más que cualquier atractor simple.

## Qué conviene hacer

- **No cambiar los destinos del modelo de hogares con los permisos.** El modelo actual es el
  mejor en RMSE.
- **Usar la vivienda nueva como capacidad del sistema abierto**, donde compiten por ella las
  mudanzas internas y las llegadas externas (`docs/validacion-poblacion.md`). Es la siguiente
  prueba: repartir las llegadas desde el extranjero según la vivienda nueva y ver si mejora la
  población por comuna.
- **Los permisos ya sirven como dato de oferta.** Los de 2015–2020 tienen correlación 0,925 con
  el aumento de viviendas entre censos (`data/vivienda/README.md`). Para escenarios de
  densificación son un insumo con fuente oficial.

## Límites

- Un permiso no es una vivienda terminada. Ñuñoa tiene muchos permisos de 2019–2021 que el censo
  2024 todavía no registra como viviendas.
- Una sola prueba fuera de muestra, en un período con estallido, pandemia y la ola migratoria
  de 2018–2019.
- Se ajustó una sola elasticidad para todas las comunas. No se ajustó nada con datos de prueba.
