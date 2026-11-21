# Viaje Real: travel cost vs friction simulator

Platanus Hack 26 Santiago ft. Buk. Track: 🌐 Simulations. Team 22.

- Jesus Rodolfo Gil Farias ([@Jrgil20](https://github.com/Jrgil20))
- Gabriel David Castellano Sierra ([@GdCastellano](https://github.com/GdCastellano))
- Daniel Enrique Bruno Silva ([@Holeekey](https://github.com/Holeekey))
- Valeria Riera ([@ingvaleriariera](https://github.com/ingvaleriariera))
- Massiel Paola Perozo Ballestero ([@massiperozo](https://github.com/massiperozo))

A deterministic engine that, for a given traveler and device profile, builds three scenarios (zero friction, balanced, local-optimized) and shows the exact trade-off between savings (USD and CLP) and a friction score. Santiago de Chile is the pilot city; the schema is city-agnostic.

![Project logo](./project-logo.png)

## Run

```bash
make setup   # create .venv and install dev dependencies
make test    # run the test suite
make lint
```

Requires Python 3.11 or later. The engine uses the standard library only.

## Layout

```text
travel_sim/domain/          entities, enums, friction score, normalization (no I/O)
travel_sim/application/     filters, ports, scenarios, simulate use case
travel_sim/infrastructure/  JSON option repository
data/cities/                per-city datasets (santiago.json)
tests/travel_sim/           unit and end-to-end tests
docs/travel-simulator/      context, data model, engine spec, seeding, roadmap
```

## Status and caveats

The Santiago seed is a draft: values without a verified source are flagged unverified (`last_verified_at: null`). Verifying them against real sources and building the UI are the next steps.
