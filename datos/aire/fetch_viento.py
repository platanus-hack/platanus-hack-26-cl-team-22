#!/usr/bin/env python3
"""Download 2023 wind roses (direction frequency) for the SINCA stations of the RM.

Source: SINCA (MMA), same server as fetch_sinca.py. Each station page lists meteorological
macros under `./RM/<code>/Met/`; the `WDIR` macro `horario_010` (10 m) returns, for a date
range, the share of hours the wind came FROM each 15-degree sector.

Output: data/aire/viento_rosa_2023.csv with one row per station and sector:
    estacion_id, sector_centro_grados, frecuencia (0-1), fecha_descarga
Stations without data for 2023 are skipped and listed on screen.

Usage:  python -m datos.aire.fetch_viento   (needs network; stdlib only)
"""
from __future__ import annotations

import csv
import datetime as dt
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "aire" / "viento_rosa_2023.csv"
STATIONS = ROOT / "data" / "aire" / "estaciones.csv"
URL = ("https://sinca.mma.gob.cl/cgi-bin/APUB-MMA/apub.tsindico2.cgi?outtype=xcl"
       "&macro=./RM/{code}/Met/WDIR//horario_010.ic&from=230101&to=231231"
       "&path=/usr/airviro/data/CONAMA/&lang=esp&rsrc=&macropath=")
HEADERS = {"User-Agent": "Mozilla/5.0 (research script; hackathon air-quality data)"}
# One line per sector: "<from>,5-<to>,5<percent>%", decimal commas and no separator,
# e.g. "187,5-202,510,3%" = sector 187.5-202.5 degrees, 10.3 % of hours.
SECTOR = re.compile(r"^(\d+),5-(\d+),5(\d+,\d)%$")


def parse_rose(text: str) -> list[tuple[float, float]]:
    """(sector centre in degrees, frequency 0-1); empty if the answer is not a full rose."""
    sectors = []
    for line in text.splitlines():
        m = SECTOR.match(line.strip())
        if m:
            centre = (float(m.group(1)) + 0.5 + 7.5) % 360
            sectors.append((centre, float(m.group(3).replace(",", ".")) / 100))
    if len(sectors) != 24:
        return []
    total = sum(f for _, f in sectors)
    return [(c, f / total) for c, f in sectors]


def main() -> None:
    with STATIONS.open(encoding="utf-8-sig", newline="") as fh:
        codes = [r["estacion_id"] for r in csv.DictReader(fh)]
    today = dt.date.today().isoformat()
    rows, missing = [], []
    for code in codes:
        req = urllib.request.Request(URL.format(code=code), headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode("latin-1")
        except OSError as exc:
            sys.exit(f"Download failed for {code}: {exc}")
        rose = parse_rose(text)
        if not rose:
            missing.append(code)
        rows += [{"estacion_id": code, "sector_centro_grados": round(c, 1),
                  "frecuencia": round(f, 5), "fecha_descarga": today} for c, f in rose]
        time.sleep(1)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{OUT.relative_to(ROOT)}: {len(rows) // 24} stations; without 2023 data: {missing}")


if __name__ == "__main__":
    main()
