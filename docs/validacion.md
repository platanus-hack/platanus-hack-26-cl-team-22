# Validación fuera de muestra

> Generado por `make validate` (`python -m experiments.validar`). No editar a mano.

Cada variable se ajusta con un período y se prueba con otro que el modelo no vio. Se compara
contra dos alternativas simples: **sin cambio** (el último valor conocido se repite) y
**tendencia** (sigue la línea de los años de ajuste). Gana el error más bajo; si los dos mejores
están a menos de 2%, es empate. Una banda del 80 % es honesta si contiene cerca
del 80 % de los valores reales.

| Variable | Prueba fuera de muestra | Métrica | Modelo | Sin cambio | Tendencia | Cobertura banda 80 % | Gana |
|---|---|---|---|---|---|---|---|
| Aire | PM2,5 por estación 2022-2024 desde 2019 (ajuste 2017-2019) | RMSE µg/m³ | 1,91 | 2,40 | 4,24 | 74% | **Modelo** |
| Hogares | Migración neta por comuna 2019-2024 (ajuste 2012-2017) | RMSE personas | 4.335 | 7.716 | 5.054 | — | **Modelo** |
| Población | Población por comuna 2024 desde 2017 (tasas 2012-2017) | RMSE personas | 16.904 | 15.046 | — | — | Sin cambio |
| Seguridad | Tasa de delitos 2024 a 1 año (comunas fuera del ajuste) | RMSE log (≈ error relativo) | 0,085 | 0,074 | 0,131 | 70% | Sin cambio |
| Seguridad | Tasa de delitos 2024 a 2 años (comunas fuera del ajuste) | RMSE log (≈ error relativo) | 0,108 | 0,124 | — | 66% | **Modelo** |

## Notas por prueba

- **Aire** (PM2,5 por estación 2022-2024 desde 2019 (ajuste 2017-2019)): Banda del motor sola: 22%. El mismo cambio en todas las estaciones: 1.94. Comando: `python -m experiments.validar`.
- **Hogares** (Migración neta por comuna 2019-2024 (ajuste 2012-2017)): Modelo determinista: sin banda. Comando: `python -m experiments.calibrar_hogares`.
- **Población** (Población por comuna 2024 desde 2017 (tasas 2012-2017)): Proyección oficial del INE: 18,391 (no es una tendencia de los años de ajuste). Sistema cerrado: no suma nacimientos ni llegadas. Comando: `python -m experiments.validar_poblacion`.
- **Seguridad** (Tasa de delitos 2024 a 1 año (comunas fuera del ajuste)): A un año, la tasa cambia poco y repetirla es difícil de batir. Comando: `python -m experiments.calibrar_seguridad`.
- **Seguridad** (Tasa de delitos 2024 a 2 años (comunas fuera del ajuste)): Sin tendencia comparable: la de 2022-2023 usa un año que el modelo no ve. Comando: `python -m experiments.calibrar_seguridad`.

## Aire: el motor de la simulación contra la realidad

Parte de las emisiones de 2017, ejecuta las medidas vigentes del plan de
descontaminación desde 2018 según su credibilidad (lectura conservadora),
y suma el cambio simulado entre 2019 y cada año de prueba al nivel medido de cada
estación en 2019. 2020 y 2021 (pandemia) no se ajustan ni se puntúan. El kernel de aire
se reajusta con las estaciones de 2017 (escala 40 km, mismo
método que `calibrar_aire.py`).

**Corrección del protocolo.** La primera versión usaba el kernel de la simulación, que está
ajustado con 2023, un año de prueba. Se reemplazó por el de 2017 después de ver ese
primer resultado; el reemplazado queda abajo como referencia, no como resultado.

| Lectura | RMSE (µg/m³) | Sesgo (µg/m³) |
|---|---|---|
| Ninguna medida se ejecuta (θ = 0) | 2,40 | 1,69 |
| **Historial de cumplimiento (la que usa la simulación)** | 1,91 | 1,11 |
| Plan tal como está escrito (θ = 1) | 1,38 | -0,077 |
| El mismo cambio del motor en todas las estaciones | 1,94 | 1,11 |
| Reemplazado: kernel ajustado con 2023 | 1,92 | 1,12 |

- Con θ = 0 el motor no agrega cambio y coincide con «sin cambio»: toda la ventaja del modelo
  viene de las medidas del plan.
- **El patrón entre comunas no está validado**: repartir el mismo cambio en todas las estaciones predice igual o mejor. El motor acierta la magnitud regional; qué comunas ganan más sale del supuesto de acople, no de la prueba.
- Sesgo positivo = el modelo predice más contaminación de la que hubo. La lectura usada en la
  simulación no se cambia por este resultado: elegirla mirando los años de prueba sería ajustar
  con la prueba.
- Banda del motor sola: 22% de cobertura (ancho medio
  1,17 µg/m³). Solo contiene la incertidumbre de ejecución.
  Sumando el error residual del motor en los años de ajuste (1,56 µg/m³:
  clima y lo que el motor no modela), cubre 74%.

Avisos:

- La credibilidad viene de la revisión de cumplimiento de 2023, dentro del período de prueba; ver las lecturas sin-ejecucion y plan-escrito.
- Acertar la baja no prueba que la causa sea el plan: el motor no tiene renovación del parque vehicular ni clima, que también bajan el PM2,5.
- La tendencia usa tres puntos (2017-2019): es frágil.
- Transporte 2017 usa el inventario 2023 (el RETC no lo trae antes); ninguna medida vigente lo toca, así que no mueve el cambio simulado.
- 9 estaciones: no alcanza para afirmar significancia estadística.
- La escala del kernel quedó en el borde de la grilla (toda la cuenca como una caja): el acople entre comunas es casi uniforme.
