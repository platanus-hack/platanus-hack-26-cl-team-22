# ADR-0002: Los hogares se modelan como flujos agregados entre comunas

- **Estado**: Aceptado
- **Fecha**: 2026-11-21

## Contexto

Hay 36 horas. Los datos de mudanzas son matrices comuna a comuna de los censos (pregunta
"comuna de residencia hace 5 años"): 2012→2017 para ajustar y 2019→2024 para probar. No hay
datos individuales que permitan calibrar agentes.

## Decisión

Los hogares se mueven como flujos agregados, ya implementados en `core/hogares.py`: una tasa
anual de salida por comuna (inercia) repartida según las proporciones de destino del censo,
con tope de viviendas. El sistema es cerrado y conserva la población total.

## Alternativas consideradas

| Opción | Pros | Contras | Por qué se descartó |
|---|---|---|---|
| Miles de agentes sintéticos | Más "ABM" a la vista | Sin datos para calibrar reglas individuales; lento para 500 réplicas | Agrega parámetros que nadie puede validar |

## Consecuencias

- Los flujos se validan directo contra la matriz 2019→2024.
- El aire no cambia destinos (no es identificable con el censo); se explica en
  `docs/modelo-hogares.md`.
- Al ser cerrado, no suma nacimientos, defunciones ni llegadas de fuera de la región:
  subestima el total de la RM hacia 2036, y con eso la métrica de ADR-0004. Un modelo abierto
  se probó y no ganó en error por comuna (`docs/validacion-poblacion.md`).
- No hay heterogeneidad individual; los tipos de hogar solo existen como pesos de lectura
  (ADR-0003).
