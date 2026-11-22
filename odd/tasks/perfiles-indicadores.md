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
- **S6 Order follows the weights.** "en el back como que si cambias los fiktros pero creo que en el front nunca lo actualizas, al menos no el orden que se ven". The dimension cards and the "Ajustar pesos" sliders are sorted by the current weight, highest first, active before inactive, and update live when the weights change.
- **S5 Fix found by the eval.** Phrases like "que se valorice con los años" should raise crecimiento (eval case 6).

## Tasks

| ID | Specs | Route | Status | Commit |
|---|---|---|---|---|
| T1 | S1 | inline | done: 29 cases, 29/29 | 338552e |
| T2 | S4 | delegated explorer (mapping trigger) | done: map in Log L6 | — |
| T3 | S2, S3, S5 | inline | done | 338552e |
| T4 | S4, S6 | lib inline; UI wiring delegated (context backstop) | done | see L12 |
| T5 | S1, S4 | inline | done: simulation 10/10, phrases 29/29 | see L12 |

## Log

- L1 (2026-11-22) User: "quiero probar muy bien como austa los filtros segu diferentes frases iniiciales con distintos contextos"
- L2 Eval run 1, 20/25. Claude's readings are fine. leerCaso's keyword regex mislabels "casa matriz", "departamento de logística", "paneles solares en mi casa" (hydro, air set to 0) and English text. Case 6, "valorice", is missed.
- L3 User: "caoaz necesitas mas perfiles para ajustar un pcoo mejor no puede ser que sean tan poco, osea, empresario joven, empredendor, depende tambien de la data pero debe alterar la relevancia de cada filtro". User approved the 9-profile table with Claude choosing the profile.
- L4 User: "y lo de bajar y subir otros indicadores o no hay otros indicadores". Answer: 4 indicators exist outside the index.
- L5 User: "mete esos 4 despues de probar muy bien que funcionen en una simulacion pero ojo no tienen que estat todos sactivos podemos seguir con 3 indicadores activos y por lo menos si es industria capaz elimina aire y es red electrica o asi"
- L6 Explorer map:
  - escasez_hidrica, red_electrica and inversion_evaluada come from viz/public/datos/inversion.json. All 52 communes have a value, they are static over years, and they are loaded async (they can be null). escasez has only 9 distinct values and 28 zeros.
  - sequia_futura comes from simulacion.json `clima` (ssp245) and changes by calendar year.
  - calcularRiesgo already handles extra variables, weight 0 and missing values.
  - The pieces that assume 3 variables: cortas/conDato, filasDe, the sliders and cards in VistaRiesgo, the guide payload, the ficha valores, irACapa, and VARIABLES_CASO plus the prompt.
  - prioridadesDe defaults missing ids to 5, so all 7 weights must be explicit.
- L7 T3 eval with Claude choosing the profile: 27/29 at first (two housing cases with "familia" or "colegios" read as general). After the rule "general solo sin pistas", 29/29. The prompt cache now hits at 1966 tokens.
- L8 The user approved the 7-column table (3 active per profile). It changes S2: inversion and empresario air 3→0; energia seg/crec 5/8→0 with sequía 8, escasez 8, red 10; mayor escasez 5.
- L9 Simulation (docs/simulacion-indicadores.md): 10/10 checks pass. All 4 indicators cover 52 communes, every commune gets an index, and no profile has more than 3 active.
  - Families, joven and general rank the same as before.
  - Inversionista, emprendedor, empresario and industria move toward Lampa, Colina, Buin and Tiltil (growth plus grid or SEIA).
  - Red flag: energia ranks the urban core first (Cerro Navia, Huechuraba, Santiago). Urban communes have no scarcity decrees and the most grid capacity, so the indicators cannot locate a plant.
  - The phrase eval on 7 variables gives 29/29. In "roben cables", Claude raised seguridad and dropped sequía to keep 3 active.
- L10 The user picked the energia weights "Red, crecimiento y seguridad (Recomendado)": red 10, crecimiento 8, seguridad 5, sequía and escasez 0. The simulation reruns 10/10, and energia now ranks Buin, Colina, Tiltil, Lampa, Paine.
- Next: T4 UI wiring, delegated to one writer (reason: long-session context backstop). Stay uncommitted until it is wired.
- L11 User: "en el back como que si cambias los fiktros pero creo que en el front nunca lo actualizas, al menos no el orden que se ven". Verified in the tour: the ranking does follow the 3 visible weights; the card order is fixed (aire first even at weight 0), and the extras' weights are ignored until T4. S6 was added to the T4 writer. The user also pasted the existing licitaciones/SEIA issue as an example; it was not acted on.
- L12 The T4 writer delivered: the 7-variable index in App (filasDe + sumarIndicadores, variablesIndice), 7 sliders, cards with only the active variables sorted by weight (ordenarPorPeso), the "aparte" block removed, and the guide and ficha values taken from the indexed row. Parent checks:
  - tsc clean, 268 tests.
  - Browser: industria ranks Buin, Colina, Tiltil with cards crecimiento, red, seguridad; familia shows cards aire, seguridad, crecimiento. No console errors after reload. The two old errors came from a mid-edit hot reload.
  - The eval found Claude raising water indicators for a hydro plant (urban top again). Fixed with the rule "En el perfil energia no las subas", pinned in the eval. Final run 39/39.
