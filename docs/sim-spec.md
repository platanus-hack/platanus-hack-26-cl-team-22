# Spec de simulación: Simulador de comunas de la Región Metropolitana

Estado al 21 de noviembre de 2026. Esta spec resume el modelo implementado. El detalle de cada
mecanismo está en [`modelo-aire.md`](./modelo-aire.md), [`modelo-hogares.md`](./modelo-hogares.md)
y [`credibilidad.md`](./credibilidad.md). Las decisiones de proyecto están en
[`contexto-proyecto.md`](./contexto-proyecto.md).

## Pregunta que responde

**¿Qué pasa con el aire de cada comuna de la Región Metropolitana entre 2026 y 2036 si los planes
públicos se cumplen como dice su historial, y no como están escritos?**

Variantes que la demo responde:

- ¿Qué pasa si una medida del plan de descontaminación no avanza?
- ¿Qué pasa si se aprueba una medida nueva? Ejemplo: extender la prohibición de leña a la Zona B.
- ¿Da lo mismo prometer mucho y cumplir poco que prometer poco y cumplirlo?

La respuesta no se conoce de antemano. Depende de tres cosas que interactúan:

- el acople del aire entre comunas;
- las mudanzas de hogares, que cambian dónde se quema leña;
- la credibilidad correlacionada de quien ejecuta cada medida.

## Clasificación (5 ejes)

Valores según [`simulation-taxonomy.md`](./simulation-taxonomy.md).

| Eje | Valor | Consecuencia |
|-----|-------|--------------|
| Tiempo | Dinámica | Ciclo anual de 2026 a 2036. El estado de un año parte del anterior |
| Cambio de estado | Discreta (paso fijo anual) | Cada año se ejecuta un ciclo completo: sorteo de medidas, emisiones, aire y mudanzas |
| Incertidumbre | Estocástica | La ejecución de medidas se sortea. Hay 500 réplicas por escenario (2.000 en la comparación de promesas) y los resultados son bandas p10–p90 |
| Acoplamiento | Constructiva (digital pura) | Sin humano en el lazo durante la simulación. La interfaz solo lee resultados precalculados |
| Representación | Basada en ecuaciones (flujos agregados) | Operador de transferencia de aire entre comunas y flujos de mudanza calibrados con el censo. No hay agentes individuales |

## Paradigma y justificación

**Monte Carlo sobre un modelo dinámico de flujos agregados, a paso anual.**

- No es DES: no hay colas ni recursos. Lo que importa es el estado anual de 52 comunas.
- No es ABM: los hogares se modelan como flujos entre comunas calibrados con el censo, no como
  agentes con reglas. Una población sintética de agentes agregaría parámetros que dos censos no
  alcanzan a identificar.
- El azar está en **si cada medida se ejecuta**. Por eso hacen falta réplicas: con el plan
  cumplido al 100 % la banda colapsa a un solo valor (18,8 µg/m³ en 2036), y con el historial
  real se abre (20,2 a 22,4 µg/m³).

## Entidades y variables de estado

| Entidad | Variables de estado | Fuente del valor inicial |
|---|---|---|
| Comuna (52) | Población | Censo 2024 (`data/censo/poblacion_viviendas.csv`) |
| Comuna | Tope de viviendas | Censo 2024, crece al ritmo 2017–2024 |
| Comuna | Emisiones primarias de PM2,5 por fuente (leña, transporte, industria, otras), en t/año | RETC 2023 (`data/emisiones/`) |
| Comuna | PM2,5 medio anual, en µg/m³ | Salida del operador de aire |
| Medida de un plan | Credibilidad θ (una por réplica) y ejecución (una por año) | Revisión ECOS-Chile 2023 del PPDA (`docs/credibilidad.md`) |
| Ejecutor | Shock común anual `z[e, t]` | Supuesto `ρ = 0,3` |

## Reglas del ciclo anual

Implementación en `core/ciclo.py`.

| Paso | Cambia el estado | Detalle |
|------|------------------|---------|
| 1. Ejecución de medidas | Qué medidas avanzan este año | Cópula gaussiana de un factor por ejecutor. θ se sortea una vez por réplica y la ejecución una vez por año (`core/credibilidad.py`) |
| 2. Emisiones | `E[c, s]` | Las medidas ejecutadas reducen su fuente en sus comunas, con una rampa de 10 años hasta el efecto completo |
| 3. Aire | `C[r]` | `C[r] = b + Σ_s k_s · Σ_c exp(−d(r, c)/L) · E[c, s]` (`core/aire.py`) |
| 4. Mudanzas | Población | `salen[i] = población[i] · r[i]`; `flujo[i, j] = salen[i] · s[i, j]`. La población regional se conserva (`core/hogares.py`) |
| 5. Acople | Leña del año siguiente | Lectura `proporcional`: la leña sigue a la población. Lectura `fija`: no cambia. Se publican ambas |

## Parámetros de entrada

| Nombre | Unidad | Valor base | Rango a explorar | Origen |
|--------|--------|------------|------------------|--------|
| `L`, escala de mezcla | km | 40 | Grilla de 3 a 40 | Ajustado dejando una estación fuera. Quedó en el borde de la grilla (ver supuestos) |
| `b`, fondo regional | µg/m³ | 0,42 | — | Ajustado con 2023 |
| `k`, concentración por tonelada | µg/m³ por t/año | Uno para todas las fuentes | — | Ajustado con 2023 |
| `r[i]`, tasa anual de salida | — | Mediana 3,1 % | — | Censo 2012→2017 |
| `s[i, j]`, destinos | — | Proporciones observadas | — | Censo 2012→2017 |
| Credibilidad del PPDA | — | Beta con media 0,347 (lectura conservadora) | Optimista; plan escrito (θ = 1) | ECOS-Chile 2023: 24 % conformes, 21 % parciales, 55 % sin evidencia |
| `ρ`, correlación anual entre medidas de un ejecutor | — | 0,3 | — | **Supuesto** |
| `ρθ`, correlación de la credibilidad entre medidas | — | 0,5 | 0 | **Supuesto**, fijado antes de correr la comparación |
| Rampa de efecto | años | 10 | 5 | Horizonte del PPDA (art. 1) |
| Réplicas | — | 500 | 2.000 en promesas | — |
| Semilla | — | 22 | — | Flujos de azar por `(semilla, réplica, id)` |

## Métricas de salida

| Nombre | Unidad | Tipo |
|--------|--------|------|
| PM2,5 medio anual por comuna y año | µg/m³ | Por réplica; se publica p10, p50 y p90 |
| PM2,5 regional ponderado por población | µg/m³ | Agregada por réplica |
| Personas que viven en comunas sobre la norma anual (20 µg/m³) | personas | Agregada por réplica |
| Aporte de cada política | µg/m³ | Mediana de la diferencia pareada con y sin la política (misma semilla) |
| Probabilidad de cumplir la norma en 2036 | — | Fracción de réplicas |
| Crecimiento de población por comuna | % desde 2024 | Determinista (flujos esperados) |
| Delitos de mayor connotación social por comuna y año | casos por 100.000 habitantes | Por réplica; se publica p10, p50 y p90 |

Todas se escriben en `viz/datos/simulacion.json` (contrato en [`plan-comunas.md`](./plan-comunas.md)).

## Validación

Cada mecanismo se ajusta con un período y se prueba con otro que el ajuste no vio, contra
alternativas simples. Se publica también donde el modelo pierde.

| Mecanismo | Prueba fuera de muestra | Modelo | Alternativas simples | Comando |
|---|---|---|---|---|
| Aire | Cambio medio 2017 → 2023 (9 estaciones) | −3,0 µg/m³ | Observado: −3,2 | `python -m experiments.calibrar_aire` |
| Aire | Error por estación del cambio 2017 → 2023 | 0,90 | Sin cambio: 3,32 · Mismo cambio en todas: 0,91 | igual |
| Aire | Niveles 2024 (10 estaciones), RMSE | 4,29 | **Persistencia de 2023: 1,91** · Media de las otras: 2,87 | igual |
| Aire v1 | Niveles 2024 anclados al residuo 2023 de cada estación | 1,91 | Persistencia: 1,91 · v0: 2,57 | `python -m experiments.aire_v1_pruebas` |
| Aire v1 | Error dejando una estación fuera: estacional / viento / residuos interpolados | 2,10 / 2,05 / 2,04 | v0: 2,05 (ninguno mejora) | igual |
| Hogares | Migración neta por comuna 2019→2024, RMSE (ajuste con 2012→2017) | **4.335** | Nadie se muda: 7.716 · Repetir 2012→2017: 5.054 | `python -m experiments.calibrar_hogares` |
| Hogares | Correlación fuera de muestra | **0,83** | Repetir 2012→2017: 0,76 | igual |
| Seguridad | Tasa DMCS 2024 a 2 años, comunas completas fuera del ajuste | **10,8 %** | Persistencia: 12,4 % · Tendencia: 13,1 % · Media prepandemia: 20,0 % | `python -m experiments.calibrar_seguridad` |
| Seguridad | Tasa DMCS 2024 a 1 año | 8,5 % | **Persistencia: 7,4 %** | igual |
| Seguridad | Valores reales dentro de la banda del 80 % (1 y 2 años) | 70 % y 66 % | Ideal: 80 % (bandas algo estrechas) | igual |

- **Caso teórico:** el kernel de simulación se valida contra la cola M/M/1 y la ley de Little
  (`tests/test_mm1.py`, `tests/test_kernel.py`).
- **Reproducibilidad:** misma semilla, misma trayectoria. Agregar o quitar una medida no cambia
  los sorteos de las demás (`tests/test_credibilidad.py`, `tests/test_ciclo.py`).
- **Casos extremos con test:** una medida con θ = 0 nunca se ejecuta y con θ = 1 siempre; la
  población total se conserva al mudarse (`tests/test_hogares.py`). Una medida en una comuna
  mejora el aire de las otras (`tests/test_ciclo.py`). Una comuna con estación parte de su nivel
  medido (`tests/test_simular.py`). Una política de seguridad con credibilidad 0 no tiene efecto y
  el efecto sobre vecinas tiene signo abierto (`tests/test_seguridad.py`). En total hay 132
  pruebas (`make test`).
- **Pendiente:** cobertura de las bandas del aire (en seguridad ya se mide: 70 % y 66 % frente al
  80 % ideal) y calibración de la credibilidad con años que el ajuste no vio. Esta última
  depende de conseguir el detalle anual de la SMA.

## Experimentos

- **Réplicas:** 500 por escenario en la simulación principal y 2.000 en la comparación de
  promesas. Las bandas son p10–p90 entre réplicas.
- **Escenarios** (misma semilla por réplica, números aleatorios comunes):
  - planes vigentes con historial real;
  - lectura optimista;
  - plan escrito (θ = 1);
  - sin políticas;
  - cada política apagada;
  - con la prohibición de leña en la Zona B;
  - las tres con la leña siguiendo a la gente.
- **Sensibilidad:** `ρθ = 0` frente a 0,5, y rampa de 5 frente a 10 años (`docs/promesas.md`).

## Resultados que sorprendieron al equipo

1. **El plan escrito y el historial real dan regiones distintas.** Cumplido al 100 %, el plan
   deja la región en 18,8 µg/m³ en 2036, bajo la norma. Con el cumplimiento observado queda en
   21,4 µg/m³ (banda de 20,2 a 22,4): el incumplimiento como cifra.
2. **La migración puede borrar la mejora del plan.** Si la leña sigue a la gente, la ciudad se
   muda hacia la Zona B (+18 % de población en 2036). Con el plan vigente la región queda en
   22,9 µg/m³, prácticamente el nivel de hoy (23,1).
3. **Importa más quién ejecuta que cuántas promesas hay.** Hay dos maneras de repartir las 18
   promesas de la Zona B:

   | Ejecución | Banda | Probabilidad de cumplir la norma |
   |---|---|---|
   | Un solo ejecutor | 2,96 µg/m³ | 0,51 |
   | 18 municipios | 1,32 µg/m³ | 0,54 |

   Lo robusto es la banda. La probabilidad de cumplir la norma depende de qué lado del umbral
   quede la mediana y su orden se invierte con cambios chicos de nivel (`docs/promesas.md`).

   Una planilla da 20,24 µg/m³ para todos los casos (`docs/promesas.md`).
4. **La prohibición en la Zona B vale más cuanta más gente se muda allí.** Su efecto mediano es
   de −3,9 µg/m³ con la leña siguiendo a la gente, frente a −3,2 con la leña fija. Es una
   interacción entre dos mecanismos, no una suma.

## Supuestos y simplificaciones

- **Aire v0 está mal identificado.** `L` quedó en el borde de la grilla (40 km) y `b` casi en 0,
  así que la cuenca se comporta como una sola caja. El modelo acierta cuánto mejora la región,
  pero **no qué comunas ganan más**. En niveles de 2024 pierde contra la persistencia. v1 ancla
  las 10 comunas con estación a su medición (empata con la persistencia); estacionalidad, viento
  e interpolación de residuos se probaron y ninguno mejora (`docs/modelo-aire.md`).
- Medias anuales y sin relieve. Viento (rosas SINCA 2023) y estacionalidad se probaron sin mejora.
- El aire no cambia a dónde se muda la gente. Con dos censos, ese término no se distingue del
  ingreso ni del precio de la vivienda.
- Las mudanzas son un sistema cerrado: no hay migración externa ni crecimiento natural.
- El censo 2017 fue de hecho y el 2024 de derecho. La matriz 2017 se reconstruyó por residencia
  habitual (`data/censo/README.md`).
- El 55 % de las medidas del PPDA no tiene evidencia pública. Se publican dos lecturas: «sin
  evidencia = no cumplida» y «sin evidencia = se excluye».
- Seguridad: inercia por comuna con datos CEAD; las políticas son ilustrativas (no hay planes
  comunales clasificados), con cobertura del 25 % y efecto sobre vecinas con signo abierto
  (`docs/modelo-seguridad.md`). Sus efectos no se pueden validar localmente.

## Stack y estructura del repo

Python 3.11 o superior (el CI usa 3.12), NumPy y SciPy en el núcleo; pandas solo para preparar datos. La interfaz es una
página estática que lee `viz/datos/simulacion.json`.

```
datos/        scripts de descarga (SINCA, RETC, censo, CEAD, PPDA)
data/         tablas limpias, con README de fuente, fecha y vacíos
core/         núcleo sin UI: aire, hogares, credibilidad, ciclo anual
experiments/  calibración, comparación de promesas y simulación -> results/, viz/datos/
tests/        pruebas del núcleo y de los datos (make test)
viz/          interfaz: solo lee simulacion.json
```
