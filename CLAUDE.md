# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Platanus Hack 26 (Simulations track) project: a Monte Carlo simulator of the 52 communes of Chile's
Región Metropolitana, 2026–2036. It projects PM2.5 (plus security, households/migration, water and climate
risk) under public plans, weighting each measure by **the probability it actually gets executed**
(credibility from historical compliance). Results are always bands (p10–p90 over 500 replicas), never a
single number. The primary user is an investor choosing a commune (`docs/adr/0006-usuario-inversionista.md`).

Language convention: identifiers, code comments and commit messages are English; docs, READMEs, UI copy
and many file/module names are Spanish (`aire`, `hogares`, `simular`, `licitaciones`). Keep extending in
the language each surface already uses.

## Commands

Python (≥3.11, venv in `.venv`, all via the Makefile):

```bash
make setup                 # create .venv, pip install -e ".[dev]"
make test                  # pytest (tests/)
make lint                  # ruff check . (line-length 100)
make simulate              # calibrate -> validate -> promises -> simulate -> viz/datos/simulacion.json
make validate              # out-of-sample tests -> docs/validacion.md, results/validacion.json, README table
make licitaciones-detalle  # per-tender contribution -> viz/datos/licitaciones.json
.venv/bin/python -m pytest tests/test_aire.py::test_name   # single test
```

CI (`.github/workflows/ci.yml`) installs `.[dev,datos]` and runs `ruff check .` and `pytest`. Raw-data
downloaders in `datos/` need `pip install -e ".[datos]"`.

Simulator UI (`viz/`, Vite + React + TS strict, Vitest):

```bash
cd viz && npm install
npm run dev                # http://localhost:5173
npm test                   # vitest run (tests live next to code: src/lib/*.test.ts)
npx vitest run src/lib/riesgo.test.ts   # single test file
npm run typecheck
npm run evaluar            # phrase -> weights evaluation (vitest.eval.config.ts, scripts/*.eval.ts)
npm run mapas              # pre-download offline relief tiles to viz/public/mapas/ (~67 MB, not in git)
```

Landing (`web/`): `make web` (dev) / `make web-build`. `npm run build` in `web/` also builds `viz/` and
copies it into `web/dist/simulador/` (`web/scripts/incluir-simulador.mjs`), so the published site is one
static bundle.

Claude proxy (`servidor-guia/`, Node ≥23.6 running `.ts` directly, no build step):

```bash
cd servidor-guia && npm install
ANTHROPIC_API_KEY=... npm start   # http://localhost:8787
npm test                          # node --test with a mocked Claude, no key needed
# then in viz/: VITE_CASO_URL=http://localhost:8787/interpretar VITE_GUIA_URL=http://localhost:8787/guia npm run dev
```

Deploy: `render.yaml` (static landing + `servidor-guia` node service); `vercel.json` builds `web/` only.

## Architecture

Data flows one way: **`datos/` → `data/` → `core/` + `experiments/` → `results/` and `viz/datos/*.json` → `viz/` UI**.

- `datos/` — per-source download/build scripts (SINCA, RETC, INE census, CEAD, DGA, ARClim, ChileCompra,
  SEIA, SMA…). Each writes cleaned tables into `data/<source>/`, whose README records URL, download date
  and gaps.
- `core/` — headless model, no UI imports. `ciclo.py` is the annual cycle: `credibilidad.py` draws which
  measures execute each year (Beta credibility, seeded per-replica streams) → each executed year moves an
  `Intervention` toward its full emissions effect → `aire.py` (`AirModel`, distance-based transfer between
  communes) gives PM2.5. `hogares.py` (`MigrationModel`) moves households, which can carry residential
  heating (wood) with them via `heating_scale`. `seguridad.py`, `clima.py` (ARClim runs, one drawn per
  replica) and `licitaciones.py` (procurement-based municipal credibility) are sibling models.
  `kernel.py`/`mm1.py`/`stats.py`/`llm_gateway.py` are generic DES/validation helpers.
- `experiments/` — scripts run as modules (`python -m experiments.X`): `calibrar_*` fit parameters into
  `results/*_calibracion.json`, `validar*` do out-of-sample tests against "no change" and "trend"
  baselines, `promesas` compares plan variants, `simular` writes the contract file
  `viz/datos/simulacion.json` (contract described in `docs/plan-comunas.md`). `make simulate` order matters:
  later steps read earlier `results/` files.
- `viz/` — only reads `viz/datos/*.json` and `viz/public/geo/`; never recomputes the model in the render loop. Logic
  lives in `src/lib/` (pure, tested), components in `src/components/`, orchestration in `src/App.tsx`. The
  map falls back automatically: online MapLibre relief → local tile pack → flat SVG "paper" map
  (`?mapa=local|plano` or key `L` to force). The households ABM runs in a Web Worker (`abm.worker.ts`) with a
  seeded PRNG (`prng.ts`) — never `Math.random()`. Risk index/ranking: `riesgo.ts`, `scoring.ts`,
  `variables.ts`, investor profiles and case parsing in `caso.ts`.
- `servidor-guia/` — the only place the Anthropic key lives (never a `VITE_*` var). `/interpretar` turns the
  user's free-text case into priority adjustments restricted to a **closed catalog** (`viz/src/lib/caso.ts`);
  anything off-catalog or whose justifying phrase doesn't appear verbatim in the case is dropped. Claude
  never writes numbers about communes. `/guia` words the explanation. Has caching, per-IP and daily caps;
  the page works without it.

## Invariants (from PR template and model docs)

- Randomness only through the model's seeded RNG (numpy `Generator` streams in `core/credibilidad.py`;
  `prng.ts` in the UI). Runs must be reproducible by seed.
- Model logic stays in `core/`; `viz/` never modifies `core/` state or `results/`.
- Every number in `results/` must be reproducible by the command named in its producing script; the README
  validation table between `<!-- validacion:inicio -->` markers is generated by `make validate` — don't edit
  it by hand.
- Model assumptions and decisions are documented in `docs/` (`sim-spec.md`, `modelo-*.md`,
  `credibilidad.md`, `adr/`). Update the relevant doc when changing a model.

## Repo workflow

- Larger features are tracked in `odd/tasks/<feature>.md` (specs, tasks, log).
- `external/dev-ai-toolkit` is a git submodule (`git submodule update --init`); project simulation skills
  live in `.claude/skills/` (`sim-scoping`, `des-montecarlo-builder`, `abm-ca-builder`, `llm-agents-sim`).
