# Plan de trabajo del equipo

- **Equipo:** 5 integrantes, ~8 h de trabajo efectivo por persona (≈ 40 h-persona).
- **Idea:** se anuncia en unas horas. Este plan es independiente de la idea; se ajusta en el kickoff.
- **Regla de oro:** el núcleo (`core/`) no tiene UI y pasa sus tests antes de empezar la visualización.

## Roles (propuesta, confirmar en el kickoff)

| Rol | Responsabilidad | Quién |
|-----|-----------------|-------|
| A. Modelo | `core/`: entidades, eventos o reglas, validación contra caso teórico | |
| B. Experimentos | `experiments/`: réplicas, intervalos de confianza, escenarios, barridos, CSV | |
| C. Visualización | `viz/`: demo en vivo que lee el núcleo, nunca lo modifica | |
| D. Agentes / integración | LLM agents (`core/llm_gateway.py`) o segundo modelador; API si hay demo interactiva | |
| E. Spec, QA y pitch | `docs/sim-spec.md`, README, guion de demo, revisión de tests y resultados | |

## Presupuesto de horas por persona (8 h)

| Bloque | Horas | Contenido |
|--------|-------|-----------|
| Kickoff conjunto | 1 | Elegir idea, pregunta, paradigma (`sim-scoping`), repartir roles |
| Trabajo de rol | 5 | Ver tabla de fases |
| Integración | 1 | Unir núcleo + experimentos + viz, arreglar lo que rompe |
| Demo y entrega | 1 | Ensayo, README, video o pitch, checklist final |

## Fases (tiempo desde que sale la idea)

| Fase | Entregable verificable | Responsables |
|------|------------------------|--------------|
| 0. Kickoff (1 h, todos) | `docs/sim-spec.md` completo y acordado | Todos, E redacta |
| 1. Modelo mínimo | `core/` corre una réplica headless e imprime métricas | A (+ D si hay agentes) |
| 2. Validación | Tests contra caso teórico, reproducibilidad y casos extremos en verde (`make test`) | A, E revisa |
| 3. Experimentos | Réplicas con intervalos de confianza y 1–2 barridos en `results/*.csv` | B |
| 4. Visualización | Demo que lee el núcleo y muestra los resultados | C (arranca con datos de ejemplo de la fase 1) |
| 5. Integración | Todo corre de punta a punta con un comando | Todos |
| 6. Entrega | README con pregunta, cómo ejecutar y hallazgos con números; demo ensayada | E lidera, todos |

C puede arrancar la UI antes de que termine la fase 2 usando un CSV de ejemplo, pero no
debe acoplarse a detalles internos del modelo.

## Flujo de trabajo en git

- Ramas cortas por tarea: `feat/<rol>-<tema>`; PR a `main` con la plantilla; al menos una revisión.
- Commits en formato Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`).
- Antes de abrir PR: `make lint && make test`.
- No commitear `.claude/settings.local.json` ni tokens.
- Si dos personas tocan el mismo archivo, coordinar por chat antes; `core/` tiene un solo dueño (rol A).

## Cómo apuntamos a la rúbrica

| Criterio (peso) | Qué hacemos |
|-----------------|-------------|
| Aspecto técnico (25) | Kernel propio validado contra teoría, semillas, réplicas con intervalos |
| Ambición (20) | Una pregunta no trivial; un experimento que una planilla no resuelve |
| Ejecución (20) | Un comando corre todo; demo ensayada; sin flujos rotos |
| Impacto (20) | Nombrar quién usaría el resultado y qué decisión cambia |
| Originalidad (15) | Buscar el ángulo que no es la primera idea; un resultado que sorprenda al equipo |

Detalle de la rúbrica y del track en `docs/evaluation-rubric.md` y `docs/track-simulations.md`.

## Checklist de entrega

- [ ] `docs/sim-spec.md` completo
- [ ] `make test` y `make lint` en verde
- [ ] Resultados multi-semilla con intervalos de confianza en `results/`
- [ ] Comparación con una línea base (reglas simples, sin el "ingrediente" del modelo)
- [ ] Demo que corre sin depender de la red (grabación o replay si usa LLM)
- [ ] `README.md`: pregunta, cómo ejecutar, hallazgos con números
- [ ] `project-description.md` y `platanus-hack-project.jsonc` completos, logo 1000x1000 ≤ 500 kB
