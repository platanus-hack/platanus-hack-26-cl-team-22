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

PM2,5 en 2036, promedio ponderado por población (base 2023: 23,4 µg/m³):

| Escenario | p10 | p50 | p90 |
|---|---|---|---|
| Ninguna política avanza | 23,4 | 23,4 | 23,4 |
| Planes vigentes, con el historial real (lectura conservadora) | 20,7 | **21,8** | 22,9 |
| Planes vigentes, lectura optimista | 19,2 | 19,6 | 21,1 |
| Planes vigentes, cumplidos al 100 % | 19,2 | **19,2** | 19,2 |
| Planes vigentes + leña prohibida en la Zona B (conservadora) | 16,0 | **19,2** | 21,3 |

Qué significa:

- **El plan escrito y el historial real dan regiones distintas.** Cumplido al 100 %, el plan
  deja la región bajo la norma anual (20 µg/m³). Con la tasa de cumplimiento observada queda
  en 21,8: el incumplimiento como cifra.
- **La Zona B es la palanca.** Extender la prohibición, aun con la misma credibilidad baja,
  logra lo mismo que cumplir al 100 % los planes vigentes. En Santiago centro, que no está
  en la Zona B, aporta −3,2 µg/m³: el acople entre comunas.
- **La industria casi no mueve el resultado** (−0,1 µg/m³ en Santiago centro).
- La métrica de personas sobre la norma salta en bloque, porque en v0 todas las comunas se
  mueven casi igual y cruzan la norma juntas. Es frágil hasta que el modelo distinga comunas.

## Siguientes versiones (v1)

Cada parámetro nuevo entra solo si mejora el error dejando una estación fuera frente a v0 y
frente a las alternativas simples. Si no mejora, se queda v0 y se dice.

1. **Fondo por estación del año**: usar la media de invierno de `pm25_anual.csv`, con la
   leña activa solo en invierno. Debería separar `b` de `k`.
2. **Relieve**: un parámetro de elevación, con un modelo digital de terreno de fuente citada.
3. **Viento**: solo si SINCA entrega dirección y velocidad por los mismos endpoints de
   `datos/aire/fetch_sinca.py`. No se fija una dirección dominante de memoria.
