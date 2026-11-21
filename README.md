# Viaje Real: travel cost vs friction simulator

Platanus Hack 26 Santiago ft. Buk. Track: 🌐 Simulations. Team 22.

- Jesus Rodolfo Gil Farias ([@Jrgil20](https://github.com/Jrgil20))
- Gabriel David Castellano Sierra ([@GdCastellano](https://github.com/GdCastellano))
- Daniel Enrique Bruno Silva ([@Holeekey](https://github.com/Holeekey))
- Valeria Riera ([@ingvaleriariera](https://github.com/ingvaleriariera))
- Massiel Paola Perozo Ballestero ([@massiperozo](https://github.com/massiperozo))

![Project logo](./project-logo.png)

**What if a traveler follows the cheapest local options instead of the default tourist ones?** For a traveler and device profile, a deterministic engine builds three scenarios (zero friction, balanced, local-optimized) and shows the exact trade-off between savings (USD and CLP) and a friction score. Hard constraints are enforced, not hoped for: an eSIM-only phone never gets a physical-SIM chip, and a traveler without a Chilean ID never gets an ID-only option. Santiago is the pilot city; the schema is city-agnostic. An optional audit measures how much a traveler would overpay by following what AI assistants recommend.

## Quick start

Python 3.11 or later; the engine uses the standard library only.

```bash
make setup    # create .venv and install dev dependencies
make demo     # three scenarios for a sample traveler
make web      # local web UI at http://127.0.0.1:8000
make test     # full test suite
make lint
```

CLI:

```bash
python -m travel_sim cities
python -m travel_sim simulate --city scl --days 7 --data-gb 10 --device esim-only --no-local-id
python -m travel_sim simulate --city scl --days 7 --data-gb 10 --device dual --format json
```

## AI-assistant audit

```bash
python -m travel_sim audit --city scl --days 7 --data-gb 10 --assistant NAME=MODEL --log audit.jsonl
```

Replay mode is the default and makes **zero network calls**. Recording answers from a real assistant requires `--mode record --allow-network` plus `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_BASE_URL`) in the environment. The adapter never stores or prints either value, refuses redirects and non-https endpoints, and caps calls, retries and response size. **No real assistant has been audited yet**, so the audit is implemented and tested but has produced no findings.

## Architecture

```text
travel_sim/domain/          entities, enums, friction score, normalization (no I/O)
travel_sim/application/     filters, ports, scenarios, simulate use case, audit
travel_sim/infrastructure/  JSON option repository, replay and Anthropic assistant adapters
travel_sim/cli.py           command line
travel_sim/web.py           local web server and static UI (loopback only)
data/cities/               per-city datasets (santiago.json)
tests/travel_sim/           unit, end-to-end, regression and security tests
docs/travel-simulator/      design documents
```

Layers depend inward only (an architecture test enforces it). Randomness exists only in the injected assistant, and tests are hermetic: they clear credentials and block any non-loopback connection.

## Data status and limits

The Santiago seed is a draft: 10 of 16 options carry a source and a verification date, mostly third-party guides and comparators to be cross-checked against official sources; 6 are flagged unverified (`last_verified_at: null`) and every output warns about it. Percentage-based costs such as exchange-house spreads are not modeled, nor is the daily trip count for transit.

An open product decision: unverified options currently take part in the scenarios, flagged but not excluded. Excluding them by default would make results stricter and less complete.

## Security notes

The web server binds to loopback only unless `--allow-remote` is passed, validates `Host`, `Origin` and `Content-Type`, caps request bodies, sends security headers and never returns exception text. It has not been deployed anywhere; `deploy-url` in `platanus-hack-project.jsonc` is still a placeholder.
