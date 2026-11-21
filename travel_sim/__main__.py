"""Module entrypoint allowing ``python -m travel_sim``."""
from __future__ import annotations

from travel_sim.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
