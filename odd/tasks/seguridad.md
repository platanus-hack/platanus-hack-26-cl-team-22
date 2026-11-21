# Feature: security as a second variable that policies move

Objective: a crime mechanism per commune (CEAD DMCS) with inertia, interventions with cited effect
ranges and an open-sign neighbor effect. Branch `feat/seguridad` (off `feat/aire-v1`).
Delivery: work-unit commits. Runner: `make test`.

## Specs

- S1. Team review (Massiel): "dos variables bien armadas"; the demo must not look like
  "solo una proyección con rangos sin simulación".
- S2. Context §4: "Seguridad | Tasa de delitos con inercia + efecto de cada intervención del
  catálogo | Efecto sobre vecinas con signo abierto".
- S3. Context §4: "La población solo afecta lo físico ... No entra a la seguridad."
- S4. Context §6: "Seguridad: dejar comunas completas fuera del ajuste"; compare against "todo
  sigue igual" and "sigue la tendencia"; "Contar cuántos valores reales caen dentro de la banda
  del 80 %".
- S5. Context §4 catalog: cameras (Piza et al., 2019) and lighting (Welsh, Farrington y
  Douglas, 2022), "Ningún estudio es chileno: bandas anchas".
- S6. Context §9: "Asumir que el delito siempre se desplaza a la comuna vecina" is not done.

## Tasks

| ID | Specs | Route | Status | Commit |
|---|---|---|---|---|
| T1 | S2, S3, S5, S6 | inline | done: `core/seguridad.py`, 14 tests | 1bd6517 |
| T2 | S4 | inline | done: 2-year error 10.8 % vs 12.4 % persistence; 1-year loses (8.5 % vs 7.4 %); bands 70 %/66 % | ae90952 |
| T3 | S1 | inline | done: variable `seguridad`, 2 illustrative toggles, aportes, validation block | this unit |

## Log

- L1 (2026-11-21): goal "trabaja detalladamente en eso"; the user clarified «eso» = the
  problems detected in the review; the stop hook pointed at security as open and doable.
- L2: Effect sizes read in the primary texts. Piza et al. 2019 (p. 141, Table 1, Fig. 2): total
  OR 1.141 (95 % CI 1.072-1.215), "Crime decreased by approximately 13%"; property 1.161
  (1.023-1.317); violent 1.050 (0.954-1.155, n.s.); active monitoring 1.172 (1.080-1.272).
  Welsh, Farrington & Douglas, Brå 2021 report (pp. 33-35, Table 2): total RES 1.16 (90 % CI
  1.06-1.27, p = .003), "crimes decreased by 14%"; property 1.14 (1.03-1.27); violent 0.99
  (0.87-1.13, n.s.). Bowers et al. 2011: diffusion more likely than displacement (catchment
  areas of a few hundred metres; cited for the sign only).
- L3: Decisions fixed before looking at outputs: coverage 25 % of a commune's property DMCS
  (scenario choice); municipal credibility mean 0.35, concentration 4 (assumption: no
  municipal execution history); neighbor effect share U(-0.1, 0.2) of the treated commune's
  reduction for communes within 6 km (assumption); with s = 0 neighbors stay unchanged and the
  treated commune does not change (tests/test_seguridad.py); ramp 10 years (same
  meaning of credibility as the PPDA); no commune GeoJSON in any branch, so neighbors are by
  centroid distance.
- L4: Results: cameras -0.6 % to -1.0 % of the treated communes' DMCS rate, lighting -0.2 % to
  -0.6 %; neighbors up to -3.5 per 100k. Well inside the yearly band. Coverage not raised after
  seeing it. Air, population and migration outputs are byte-identical to before.
