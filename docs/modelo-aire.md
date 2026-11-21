# Modelo de aire (v0)

Estado al 21 de noviembre de 2026. Mecanismo 1 del modelo (ver
[`contexto-proyecto.md`](./contexto-proyecto.md), sección 4). Código en `core/aire.py`;
calibración en `experiments/calibrar_aire.py`; resultados en `results/aire_calibracion.json`.

Reproducir:

```
python -m experiments.calibrar_aire
```

## Ecuación

```
C[r] = b + Σ_s k_s · Σ_c T[r, c] · E[c, s]
T[r, c] = exp(−d(r, c) / L)
```

| Símbolo | Qué es | Unidad | Origen |
|---|---|---|---|
| `C[r]` | PM2,5 medio anual en la comuna o estación `r` | µg/m³ | Salida |
| `E[c, s]` | Emisiones primarias de PM2,5 de la comuna `c`, fuente `s` | t/año | RETC, `data/emisiones/` |
| `T[r, c]` | Peso de transferencia de `c` a `r`. Los valores fuera de la diagonal son el acople entre comunas | — | Núcleo exponencial, distancia entre centroides |
| `L` | Escala de mezcla en la cuenca | km | Ajustada (error dejando una estación fuera) |
| `b` | Fondo regional (aerosol secundario, aporte externo) | µg/m³ | Ajustado |
| `k_s` | Concentración por tonelada transferida | µg/m³ por t/año | Ajustado; un solo `k` para leña, transporte e industria |

Un solo `k` para todas las fuentes es una decisión física: todas son toneladas de PM2,5
primario. Con 10 estaciones no alcanza para estimar un `k` por fuente.

El núcleo solo aplica el operador. `T`, `b` y `k_s` se estiman fuera de `core/`, así que el
núcleo de transporte se puede mejorar sin tocar el modelo.

## Ajuste y prueba

Se ajusta con 2023, el único año con las cuatro fuentes del RETC, y se prueba con datos que el
ajuste no vio.

| Prueba | Modelo | Alternativas simples |
|---|---|---|
| Ajuste 2023, error dejando una estación fuera (10 estaciones) | 2,05 µg/m³ (R² = 0,55) | Media de las otras estaciones: 2,83 |
| Niveles 2024 (10 estaciones) | 4,29 µg/m³ | Media de las otras: 2,87 · Persistencia de 2023: **1,91** |
| Cambio 2017 → 2023, media (9 estaciones) | **−3,0 µg/m³** | Observado: **−3,2** |
| Cambio 2017 → 2023, error por estación | 0,90 µg/m³ | Sin cambio: 3,32 · Mismo cambio en todas: 0,91 |
| Cambio 2017 → 2023, correlación del patrón | 0,26 | — |

Qué significa:

- **El modelo acierta cuánto baja la región** cuando bajan las emisiones (la leña cayó 24 %
  entre 2017 y 2023), con datos que no usó para ajustarse.
- **No acierta qué estaciones mejoran más.** Su patrón espacial no le gana a «el mismo cambio
  en todas». Con `L = 40 km` la cuenca se comporta como una sola caja.
- Para la demo: v0 puede responder «¿cuánto mejora la región si se prohíbe la leña en la
  Zona B?», pero **no** «¿qué comunas ganan más?».
- En niveles de 2024 pierde contra la persistencia. Más de la mitad del error viene de un
  dato: la industria declarada de Las Condes salta de 25 a 362 t entre 2023 y 2024. Con la
  industria de 2023, el error baja de 4,29 a 2,57.

## Supuestos y limitaciones

- **Transporte** solo existe por comuna en 2023; 2017 y 2024 usan el valor de 2023.
- **«Otras»** (incendios, quemas agrícolas) queda en el estado con coeficiente 0. Es
  episódica: 30.842 t en 2017 contra 1.855 t en 2023, sobre todo incendios de verano que no
  mueven la media anual en proporción.
- **Industria del RETC**: la cobertura cambia entre años (110 t en 2017, 616 t en 2024). El
  salto de Las Condes queda reportado al frente 2 para revisar.
- Una comuna sin fila en el RETC para una fuente cuenta como 0 t.
- **`L` quedó en el borde de la grilla (40 km)** y **`b` dio casi 0 (0,42 µg/m³)**. Con una
  escala tan grande la señal es casi pareja entre estaciones, y `b` y `k` se confunden. Un
  fondo cercano a 0 no es creíble físicamente (el aerosol secundario existe): es la primera
  señal de que v0 está mal identificado.
- Medias anuales: sin estacionalidad, viento ni relieve.

## Simulación 2026–2036

`python -m experiments.simular` (`core/ciclo.py`): 500 réplicas, semilla 22, emisiones de
2023 como punto de partida. Supuestos en `meta.supuestos` de `viz/datos/simulacion.json`.

Políticas con efecto citado:

- prohibición de leña en la Zona A (art. 74, vigente);
- −30 % de la industria (arts. 57-58, vigente, aplicado como cota superior);
- extender la prohibición de leña a la Zona B (propuesta).

PM2,5 en 2036, promedio ponderado por la población de 2036, con la leña fija (base 2023:
23,1 µg/m³, con las comunas con estación ancladas a su medición). Con la leña siguiendo a
quienes se mudan, ver [`modelo-hogares.md`](./modelo-hogares.md):

| Escenario | p10 | p50 | p90 |
|---|---|---|---|
| Ninguna política avanza | 22,9 | 22,9 | 22,9 |
| Planes vigentes, con el historial real (lectura conservadora) | 20,2 | **21,4** | 22,4 |
| Planes vigentes, lectura optimista | 18,8 | 19,3 | 20,4 |
| Planes vigentes, cumplidos al 100 % | 18,8 | **18,8** | 18,8 |
| Planes vigentes + leña prohibida en la Zona B (conservadora) | 15,6 | **18,5** | 21,1 |

Qué significa:

- **El plan escrito y el historial real dan regiones distintas.** Cumplido al 100 %, el plan
  deja la región bajo la norma anual (20 µg/m³). Con la tasa de cumplimiento observada queda
  en 21,4: el incumplimiento como cifra.
- **La Zona B es la palanca.** Extender la prohibición, aun con la misma credibilidad baja,
  logra en la mediana algo mejor que cumplir al 100 % los planes vigentes, pero con una banda
  ancha (15,6 a 21,1). En Santiago centro, que no está en la Zona B, aporta −3,2 µg/m³: el
  acople entre comunas.
- **La industria casi no mueve el resultado** (−0,2 µg/m³ en Santiago centro).
- La comparación entre prometer mucho y cumplir poco, y prometer poco y cumplirlo, está en
  [`promesas.md`](./promesas.md).
- La métrica de personas sobre la norma salta en bloque, porque el modelo mueve a todas las
  comunas casi igual y cruzan la norma juntas.

### Comunas destacadas (contraste medido)

La interfaz destaca pocas comunas con contraste (`comunas_destacadas`), con una regla fija:
las dos de mayor y las dos de menor nivel medido, más las de la Zona B con estación. Su nivel
de partida es el medido por su estación; el cambio hasta 2036 es modelado (planes vigentes,
lectura conservadora, leña fija):

| Comuna | Medido 2023 | 2036, p50 (p10–p90) |
|---|---|---|
| El Bosque | 28,1 | 26,3 (25,0–27,6) |
| Cerro Navia | 26,5 | 24,8 (23,6–26,0) |
| Puente Alto | 21,1 | 19,4 (18,2–20,6) |
| Las Condes | 19,1 | 17,5 (16,3–18,6) |
| Talagante | 21,6 | 20,5 (19,7–21,3) |

## v1: qué probamos para distinguir comunas

`python -m experiments.aire_v1_pruebas` (resultados en `results/aire_v1_pruebas.json`). Cada
candidato se mide con el error dejando una estación fuera en 2023 (10 estaciones), eligiendo
sus parámetros sin mirar la estación que se predice. Solo entra si le gana a v0.

| Candidato | Error (µg/m³) | ¿Entra? |
|---|---|---|
| v0 (núcleo por distancia) | 2,05 | — |
| Media de las otras estaciones | 2,83 | — |
| Fondo distinto en invierno y resto del año, leña solo en invierno | 2,10 | No: peor |
| Transporte a favor del viento (rosas de viento SINCA 2023, un parámetro) | 2,05 | No: el mejor peso del viento es 0 |
| v0 + interpolación de los residuos de las otras estaciones | 2,04 | No: los residuos no tienen patrón espacial |

| Niveles 2024 en las estaciones | Error (µg/m³) |
|---|---|
| v0 | 2,57 |
| **v0 anclado al residuo 2023 de cada estación** | **1,91** |
| Persistencia de 2023 | 1,91 |

Qué significa:

- **Con 10 estaciones, las emisiones primarias del RETC no explican dónde está el peor aire.**
  Ni la estación del año ni la dirección del viento mejoran el patrón espacial. Lo más
  probable es que pesen el aerosol secundario y la acumulación nocturna de aire frío en el
  poniente, que el modelo no tiene.
- **Lo que sí funciona es anclar el nivel a lo medido** donde hay estación: el error en 2024
  baja de 2,57 a 1,91. Por eso v1 adopta «nivel medido + cambio modelado» (el método estándar
  en proyecciones de calidad del aire): las 10 comunas con estación parten de su medición y el
  modelo calcula cuánto cambian. Las otras 42 usan el modelo solo (`nivel_base: modelado`).
- El ajuste por comuna mueve el nivel, nunca el efecto de una política (hay un test).

Las rosas de viento se descargan con `python -m datos.aire.fetch_viento` (SINCA, macro
`Met/WDIR/horario_010`); ver `data/aire/README.md`.

## Siguientes versiones

1. **Relieve**: un parámetro de elevación, con un modelo digital de terreno de fuente citada.
2. **Viento por hora**: SINCA entrega `WSPD` por hora; un transporte que use dirección y
   velocidad hora a hora en invierno, no solo la rosa anual.
3. Más estaciones o años: con 10 receptores, cada parámetro nuevo es difícil de identificar.
