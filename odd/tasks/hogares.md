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
| T2 | S1, S3, S5 | inline | done: `core/hogares.py`, 13 tests (conservation, capacity) | 2845953 |
| T3 | S2, S6 | inline | done: RMSE 4,335 vs 5,054 (repeat) vs 7,716 (no moves) | 07c192b, 887a6d2 |
| T4 | S4, S7 | inline | done: heating_scale in the cycle; population variable, flows and net migration in `simulacion.json` | 7a548dc + this unit |

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
- L4: Out-of-sample errors correlate 0.36 with new dwellings 2017-2024 (Ñuñoa +32 %); not
  added as a term (2024 dwellings belong to the test period). Santiago lost 30k despite +24 %
  dwellings: period effect.
- L5: Zona B grows from 1,140,547 to 1,350,891 by 2036 (+18 %); housing cap never binds.
  With heating following people: no policy 24.7, base 23.2 (migration offsets the plan's
  ~1.5 µg/m³ improvement). Zona B ban, paired median: -3.9 vs -3.2 µg/m³ with fixed heating
  (+19 %, interaction). Toggles use `fija`. The loop is one-way (air does not move people).
- L6: Process slip: the census merge commit and one lint failure were committed before checks
  (pipe hid ruff's exit code); fixed with a follow-up commit, checks now run with pipefail.
