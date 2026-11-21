# Feature: households mechanism (hogares)

Objective: households move between communes using the census matrices, and moves change heating
emissions and air. Branch `feat/datos-aire`. Delivery: work-unit commits. Runner: `make test`.

## Specs

- S1. Use Massiel's census matrices (`data/censo/`): "La diagonal cuenta a quienes no se
  mudaron. La tasa de salida de una comuna es su fila sin la diagonal dividida por el total de
  la fila. Esa es la inercia."
- S2. "Según el plan, ajustás con 2012→2017 y probás con 2019→2024."
- S3. Context §4: "Inercia (la mayoría no se muda) y tope de viviendas por comuna."
- S4. Context §4: "La población nueva cambia las emisiones del año siguiente."
- S5. Context §10: "la población total se conserva al mudarse."
- S6. Validation caveat (Massiel): "2019→2024 incluye el estallido y la pandemia ... Conviene
  decirlo en la validación."
- S7. Massiel's review: the demo must not look like "solo una proyección con rangos sin
  simulación"; "dos variables bien armadas".

## Tasks

| ID | Specs | Route | Status | Commit |
|---|---|---|---|---|
| T1 | S1 | inline | done: data merged, reference figures verified | 43eb369 |
| T2 | S1, S3, S5 | inline | pending: `core/hogares.py` + tests | |
| T3 | S2, S6 | inline | pending: calibration and test, `docs/modelo-hogares.md` | |
| T4 | S4, S7 | inline | pending: heating feedback in the cycle, population variable, flows in `simulacion.json` | |

## Log

- L1 (2026-11-21, user, verbatim excerpt): "Jesús, ya están las matrices del censo para el
  modelo de hogares. Están en la rama feat/datos-censo, carpeta data/censo/ ..."
- L2: Reference figures verified: 910,411 / 993,528 moves; 4,975,480 / 5,471,843 stayers.
  Out-rate correlation between periods 0.953; net migration 0.757. Net gainers are Zona B
  communes (Lampa, Colina, Buin).
- L3: Decision: destinations replay observed 2012→2017 shares; the air→moves term is not
  identifiable from cross-section (confounded by income/housing), default 0. Heating feedback
  has two readings (per-capita upper bound, fixed lower bound). RETC residential leña is
  top-down (dwellings × penetration × consumption × factor).
