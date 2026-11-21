# viz/

Visualización de la simulación. Reglas:

- Lee el estado del núcleo (`core/`) o los CSV de `results/`; **nunca los modifica**.
- Sin lógica de modelo dentro del bucle de render.
- Si es web: TypeScript + Canvas, simulación en un Web Worker, PRNG con semilla (nunca `Math.random()`).
- Si es Python: cualquier librería, siempre separada de `core/`.

Decidir el stack en el kickoff (ver `.claude/skills/sim-scoping`, Paso 4).
