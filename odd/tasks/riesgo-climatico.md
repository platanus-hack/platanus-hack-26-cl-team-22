# Climate risk indices computed by the simulation

Objective: each replica draws one ARClim climate-model run and the engine computes water, flood and heat risk per commune and year, from each run's change against 1991–2020.
Branch: `feat/riesgo-climatico`. Delivery: ask-on-risk. Test runner: `make test` (pytest), `ruff check .`.

## Specs

- **S1** (handoff, pendiente 2, verbatim): «**Índices de riesgo calculados por la simulación** (objetivo de capital internacional, decidido por el equipo). ARClim es insumo, no resultado: cada réplica debe sortear una corrida de modelo climático y el motor calcula el riesgo (hídrico, inundación, calor) por comuna y año, usando el **cambio** respecto de 1991–2020 de cada corrida (los niveles absolutos tienen sesgo).»
- **S2** (handoff, verbatim): «Validar contra los decretos de escasez de la DGA (24 comunas con decreto, 28 sin).»
- **S3** (assumptions, not user requirements; recorded so they can be challenged):
  - One draw per replica picks a GCM uniformly, then one of its runs, from the runs present in **every** indicator used. All three risks in a replica come from the same climate world.
  - The signal for year *t* is the run's mean over the 20 years *t*−10..*t*+9, the same window length ARClim uses (2041–2060). The change is taken against the same run's 1991–2020 mean. Relative change (%) for precipitation amounts; absolute change for days, percentage points and degree-days.
  - Components: water = `pr_sum` (%), `drought_periods` (pp); flood = `maximum_daily_precipitation` (%), `days_over_50mm` (days); heat = `hot_days` (days), `degdays_above_25` (degree-days). `eto_mean` is left out because only 10 GCMs carry it.
  - Both scenarios (`ssp245`, `ssp585`) are exported; years 2026–2060 (2060 is the last year whose window 2050–2069 fits the data).
  - Each risk reports its components in physical units with p10/p50/p90 across replicas. **No composite score**: weights would be invented numbers.
  - Existing air, households and security outputs stay byte-identical; the climate draw uses its own keyed stream.
  - The DGA check is cross-sectional (communes with vs without a decree), because model years are not aligned with real years. It is compared against trivial baselines and reported honestly even if it loses.
- **Out of scope until decided:** integration into the viz ranking (`caso.ts` catalog, the three variables, `servidor-guia` prompts); coupling heating degree-days into the air model (changes validated outputs); a composite index.

## Tasks

| ID | Specs | Route | Status | Evidence |
|---|---|---|---|---|
| T1 | S1, S3 | inline | done | `6f29de4`: `core/clima.py`; RED (import error) → GREEN 9 tests |
| T2 | S1, S3 | inline | done | `f8263d2`: `clima` block; every other key equal to the pre-change snapshot |
| T3 | S2, S3 | inline | done | `fa1a35e`: AUC model 0.605, outside Santiago province 0.917, base precipitation 0.125; README table unchanged |

## Log

- **L1** (2026-11-21, user, verbatim): «porfa» — answering «Lo que sigue para mejorar la predicción es el pendiente 2: que la simulación calcule los índices de riesgo a partir de ARClim.»
- **L2** (2026-11-21, evidence): ARClim series are not in LFS. GCMs per indicator (ssp245): 28 for the water and flood indicators, 18 for heat, 10 for `eto_mean`; 18 common to the six chosen indicators. DGA: 186 decree rows, 24 communes, 2008–2023; 15 rows declared by province. `simulacion.json` is 1.5 MB, 500 replicas, seed 22, keyed streams `SeedSequence([seed, replica, key])` in `core/credibilidad.py`.
- **L3** (2026-11-21, evidence): 19 runs (17 GCMs ssp245, 18 ssp585) carry all six indicators. Santiago, ssp245, 2041–2060 vs 1991–2020, p10/p50/p90: hot days +23/+40/+51; precipitation −20/−5/+5 %; drought frequency −7/+2/+11 pp. Consistent with the ARClim README ensemble (hot days 71.0 → 107.6).
- **L4** (2026-11-21, decision): values rounded to 1 decimal; `simulacion.json` grows from 1.50 MB to 2.63 MB (gzip 208 KB → 324 KB). If the viz never reads `clima`, move it to its own file when integrating.
- **L5** (2026-11-21, evidence): the water check loses. The model's drought-frequency change ranks communes with a decree above chance (AUC 0.61), but «outside the Santiago province» ranks them far better (0.92). Decrees probably track exposure (rural, irrigation) more than climate change. The engine measures how much the climate changes, not how exposed a commune is today. Next: an exposure component (rural share, water source), and the viz decision.
- **L6** (2026-11-21, checks): `make test` 289 passed; `ruff check .` clean; viz typecheck + 215 vitest passed (after T2).
