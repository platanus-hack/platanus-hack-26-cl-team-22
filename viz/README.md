# viz/

Visualización de la simulación. Reglas:

- Lee el estado del núcleo (`core/`) o los CSV de `results/`; **nunca los modifica**.
- Sin lógica de modelo dentro del bucle de render.
- Si es web: TypeScript + Canvas, simulación en un Web Worker, PRNG con semilla (nunca `Math.random()`).
- Si es Python: cualquier librería, siempre separada de `core/`.

Decidir el stack en el kickoff (ver `.claude/skills/sim-scoping`, Paso 4).

## Interfaz (Frente 8)

Página estática de una sola pantalla: Vite + React + TypeScript (strict) + deck.gl (vista de mapa
sin teselas ni token, funciona sin red). Solo lee `datos/simulacion.json`; no hay backend, ni
analítica, ni peticiones externas. Las tipografías vienen empaquetadas (`@fontsource`).

### Cómo correrla

```bash
cd viz
npm install
npm run dev        # http://localhost:5173
npm run typecheck  # tsc --noEmit
npm test           # Vitest (lógica pura: escenarios, puntajes, hallazgos, validador, polígonos)
npm run build      # genera viz/dist, estática, con rutas relativas
npm run preview    # sirve viz/dist
```

### Dónde van los datos

| Archivo | Quién lo pone | Qué pasa si falta |
|---|---|---|
| `viz/public/datos/simulacion.json` | El pipeline de Python | Se usa `viz/ejemplo/simulacion.json` (se sirve como `datos/ejemplo.json` por un plugin de `vite.config.ts`, sin copiarlo a mano) y aparece la etiqueta "Datos de ejemplo" si `meta.es_ejemplo` es true |
| `viz/public/geo/comunas_rm.geojson` | Frente de cartografía | Cada comuna se dibuja como un círculo en su lat/lon |

Si el JSON no cumple el contrato (`docs/plan-comunas.md`), la página muestra un estado de error con la
lista de problemas. `flujos`, `aportes`, `origen_aire`, `validacion` y la variable `seguridad` son opcionales; si `origen_aire`
trae una entrada mal formada (fracción fuera de 0 a 1, suma mayor que 1) se rechaza el archivo con un mensaje claro.
Si falta `origen_aire`, la ficha no muestra la sección "De dónde viene su aire" ni las líneas del mapa.
Los polígonos se emparejan con el JSON por `codigo` y, si no calza, por nombre sin tildes ni mayúsculas.

### Estilo

Todo color, tamaño de letra y espacio está en `src/tokens.css` (rampa de PM2,5 `--rampa-1..7`, acento
`--acento`, paleta divergente `--div-1..5`, tipografías `--f-serif`, `--f-sans` (IBM Plex Sans), `--f-mono`). Los colores del mapa se leen de esas variables.

### Estructura

```
src/lib/        lógica pura y sus tests: validate, load, scenario, scoring, findings, geo, color, format, data,
                vista (encuadre), diferencia, origen
src/components/ MapaComunas, ControlesVista, PanelPoliticas, PerfilHogar, ListaRanking, FichaComuna, GraficoLinea, ControlTiempo, Leyenda
src/App.tsx     estado y composición;  src/main.tsx  carga de datos y estados de error
```
