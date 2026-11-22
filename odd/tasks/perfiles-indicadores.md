# perfiles-indicadores

Objective: more investor profiles, chosen by Claude, each with 3 active indicators out of 7 in the risk index.
Branch: feat/pulir-filtros · Delivery: ask-on-risk · Tests: viz `npx vitest run`, servidor-guia `npm test`, model eval `npm run evaluar` (viz/).

## Specs

- **S1 Evaluation harness.** "quiero probar muy bien como austa los filtros segu diferentes frases iniiciales con distintos contextos". A bank of opening phrases runs the app's path (profile → Claude → weights → top 3) and writes docs/evaluacion-casos.md.
- **S2 More profiles.** "necesitas mas perfiles para ajustar un pcoo mejor no puede ser que sean tan poco, osea, empresario joven, empredendor, depende tambien de la data pero debe alterar la relevancia de cada filtro". The user approved 9 profiles. Initial grades for aire / seguridad / crecimiento:

  | Profile | Aire | Seg | Crec |
  |---|---|---|---|
  | Familia con niños | 10 | 8 | 3 |
  | Adulto mayor | 10 | 8 | 0 |
  | Joven que arrienda | 3 | 8 | 5 |
  | Inversionista inmobiliario | 3 | 5 | 10 |
  | Emprendedor / comercio | 0 | 8 | 10 |
  | Empresario joven / oficina | 3 | 5 | 8 |
  | Industria y logística | 0 | 5 | 8 |
  | Energía (hidro, solar) | 0 | 5 | 8 |
  | Evaluación general | 5 | 5 | 5 |

- **S3 Claude picks the profile.** Claude chooses the profile from the closed list while reading the case. The keyword detector (leerCaso) is only the fallback when Claude does not answer.
- **S4 Four more indicators in the index.** "mete esos 4 despues de probar muy bien que funcionen en una simulacion pero ojo no tienen que estat todos sactivos podemos seguir con 3 indicadores activos y por lo menos si es industria capaz elimina aire y es red electrica o asi".
  - The indicators are sequía futura, escasez hídrica, red eléctrica and inversión evaluada (viz/src/lib/inversion.ts).
  - Each profile keeps 3 active indicators out of the 7. For example, industry drops aire and uses red eléctrica.
  - Claude can raise or lower them.
  - They enter only after they are tested in a simulation.
- **S5 Fix found by the eval.** Phrases like "que se valorice con los años" should raise crecimiento (eval case 6).

## Tasks

| ID | Specs | Route | Status | Commit |
|---|---|---|---|---|
| T1 | S1 | inline | done (uncommitted): 25 cases, first run 20/25 | — |
| T2 | S4 | delegated explorer (mapping trigger) | pending: map the 4 indicators (data per year/commune, direction) and how they would enter calcularRiesgo | — |
| T3 | S2, S3, S5 | inline | pending | — |
| T4 | S4 | inline | pending: indicators in the index, 3 active per profile, Claude adjusts | — |
| T5 | S1, S4 | inline | pending: extend the eval to 7 indicators and run the simulation | — |

## Log

- L1 (2026-11-22) User: "quiero probar muy bien como austa los filtros segu diferentes frases iniiciales con distintos contextos"
- L2 Eval run 1, 20/25. Claude's readings are fine. leerCaso's keyword regex mislabels "casa matriz", "departamento de logística", "paneles solares en mi casa" (hydro, air set to 0) and English text. Case 6, "valorice", is missed.
- L3 User: "caoaz necesitas mas perfiles para ajustar un pcoo mejor no puede ser que sean tan poco, osea, empresario joven, empredendor, depende tambien de la data pero debe alterar la relevancia de cada filtro". User approved the 9-profile table with Claude choosing the profile.
- L4 User: "y lo de bajar y subir otros indicadores o no hay otros indicadores". Answer: 4 indicators exist outside the index.
- L5 User: "mete esos 4 despues de probar muy bien que funcionen en una simulacion pero ojo no tienen que estat todos sactivos podemos seguir con 3 indicadores activos y por lo menos si es industria capaz elimina aire y es red electrica o asi"
- Next: T2 explorer map.
