# docs/travel-simulator

Design documents for the Viaje Real simulator.

| File | Content |
|------|---------|
| `context.md` | Problem, premises, scope, AI-audit angle and the SIM/device constraint, with sources |
| `data-model.md` | Entities, normalization and the `friction_score` definition |
| `engine-spec.md` | Filtering rules, the three scenarios and the AI-audit pipeline |
| `seeding-strategy.md` | Seed structure, storage trade-off and batch updates |
| `roadmap.md` | Layers and the MVP plan |

`context.md` was written by hand. The other four started as drafts produced with the Antigravity CLI (`agy`) and were reviewed only partially. Where they differ from the code, **the code and its tests are the source of truth**. The sample prices in `seeding-strategy.md` are illustrative; the real seed is `data/cities/santiago.json`, where each option carries its own source and verification date.
