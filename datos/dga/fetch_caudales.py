"""Download DGA monthly streamflow (via CR2) and OSM river lines for the Región Metropolitana.

Sources:
- Caudales medios mensuales (m³/s) de la DGA, compilados por (CR)2, versión 2018, CC0:
  https://www.cr2.cl/datos-de-caudales/  (809 stations, 1913-02 to 2018-02). The zip link carries a
  per-request token, so it is read from the page (the link whose path contains
  `cr2_qflxamon_2018-zip`) on every run.
- Ríos y esteros: OpenStreetMap vía Overpass API (ODbL), `waterway=river` dentro del bbox de la RM
  y `waterway=stream` cuyo nombre coincide con el curso de una estación conservada.

Station rules: inside one of the 52 commune polygons, name starting with Río/Estero/Quebrada,
>= 15 valid years in 1980-2017 and >= 4 in 2010-2017 (a year is valid with >= 10 months of data).

Usage (from the repo root):  python -m datos.dga.fetch_caudales   (standard library only)
Output: data/dga/caudales_rm_mensual.csv, data/dga/estaciones_caudal_rm.csv, manifest.json
(merged with the decrees entries), viz/public/datos/caudales.json, viz/public/geo/rios_rm.geojson.
Raw downloads are cached under data/raw/dga/ (ignored by git); delete them to refresh.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import itertools
import json
import math
import re
import statistics
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from datos.comun import ROOT, USER_AGENT, clave

PAGE = "https://www.cr2.cl/datos-de-caudales/"
ZIP_MARK = "cr2_qflxamon_2018-zip"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
OVERPASS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
BBOX = (-34.35, -71.75, -32.85, -69.70)  # south, west, north, east
RAW = ROOT / "data" / "raw" / "dga"
OUT = ROOT / "data" / "dga"
COMUNAS_GEO = ROOT / "viz" / "public" / "geo" / "comunas_rm.geojson"
JSON_OUT = ROOT / "viz" / "public" / "datos" / "caudales.json"
RIOS_OUT = ROOT / "viz" / "public" / "geo" / "rios_rm.geojson"

PERIOD, BASE, DROUGHT = (1980, 2017), (1980, 2009), (2010, 2017)
MIN_MONTHS, MIN_YEARS, MIN_YEARS_DROUGHT, MIN_BASE_YEARS = 10, 15, 4, 10
SIMPLIFY_DEG, MIN_UNNAMED_KM = 0.0008, 2.0
MISSING = -9999.0
SPLIT = re.compile(r" (?:En|Antes|Ante|Despues|Bajo|Sobre|Aguas|Rinconada) ", re.IGNORECASE)
ACCENTS = {
    "rio": "Río",
    "arrayan": "Arrayán",
    "jose": "José",
    "cajon": "Cajón",
    "penon": "Peñón",
    "maria": "María",
    "martin": "Martín",
    "sebastian": "Sebastián",
    "ramon": "Ramón",
    "angel": "Ángel",
    "volcan": "Volcán",
    "perez": "Pérez",
}


# --- pure functions ---------------------------------------------------------------------------


def restore_accents(text: str) -> str:
    """Spanish accents for display, word by word, from a small dictionary ("Rio" -> "Río")."""
    return " ".join(ACCENTS.get(w.lower(), w) for w in text.split())


def rio_name(station_name: str) -> str:
    """Watercourse of a station name: the text before « En », « Antes », « Bajo », ..."""
    return restore_accents(SPLIT.split(station_name, maxsplit=1)[0].strip())


def river_key(name: str) -> str:
    """Matching key of a watercourse: no accents, no case, no leading «Río» ("Río Maipo" -> maipo)."""
    k = clave(name)
    return k[3:] if k.startswith("rio") and len(k) > 3 else k


def ring_contains(ring: list, x: float, y: float) -> bool:
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring[:-1] if ring[0] == ring[-1] else ring):
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


class Comunas:
    """Point-in-polygon over the commune polygons (Polygon geometries, holes respected)."""

    def __init__(self, features: list[dict]):
        self.items = []
        for f in features:
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            for rings in polys:
                xs = [p[0] for p in rings[0]]
                ys = [p[1] for p in rings[0]]
                self.items.append(
                    (f["properties"]["codigo"], (min(xs), min(ys), max(xs), max(ys)), rings)
                )

    @classmethod
    def load(cls, path: Path = COMUNAS_GEO) -> Comunas:
        return cls(json.loads(path.read_text(encoding="utf-8"))["features"])

    def code_at(self, lon: float, lat: float) -> str | None:
        for code, (x0, y0, x1, y1), rings in self.items:
            if (
                x0 <= lon <= x1
                and y0 <= lat <= y1
                and ring_contains(rings[0], lon, lat)
                and not any(ring_contains(h, lon, lat) for h in rings[1:])
            ):
                return code
        return None


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def aggregate(monthly: dict[tuple[int, int], float]) -> dict:
    """Annual means, regime and indicators of one station from {(year, month): m3/s}."""
    y0, y1 = PERIOD
    in_period = {k: v for k, v in monthly.items() if y0 <= k[0] <= y1}
    by_year: dict[int, list[float]] = {}
    for (y, _), v in in_period.items():
        by_year.setdefault(y, []).append(v)
    annual = {y: mean(vs) for y, vs in by_year.items() if len(vs) >= MIN_MONTHS}
    regime = []
    for m in range(1, 13):
        regime.append(mean([v for (_, mm), v in in_period.items() if mm == m]))

    def span(lo: int, hi: int) -> list[float]:
        return [v for y, v in annual.items() if lo <= y <= hi]

    base_vals, drought_vals = span(*BASE), span(*DROUGHT)
    base = mean(base_vals) if len(base_vals) >= MIN_BASE_YEARS else None
    drought = mean(drought_vals)
    change = round((drought / base - 1) * 100, 1) if base and drought is not None else None
    monthly_vals = list(in_period.values())
    avg = mean(monthly_vals)
    cv = round(statistics.pstdev(monthly_vals) / avg, 2) if avg else None
    return {
        "annual": annual,
        "regime": regime,
        "medio": mean(list(annual.values())),
        "base": base,
        "sequia": drought,
        "cambio": change,
        "cv": cv,
        "valid_years": len(annual),
        "valid_years_drought": len(drought_vals),
    }


def r2(x: float | None) -> float | None:
    return None if x is None else round(x, 2)


def dp_simplify(pts: list, tol: float) -> list:
    """Douglas-Peucker (iterative); keeps the order of the vertices."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = pts[a], pts[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        far, idx = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            d = (
                math.hypot(px - ax, py - ay)
                if norm == 0
                else abs(dy * (px - ax) - dx * (py - ay)) / norm
            )
            if d > far:
                far, idx = d, i
        if far > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def length_km(pts: list) -> float:
    total = 0.0
    for (x0, y0), (x1, y1) in itertools.pairwise(pts):
        total += math.hypot((x1 - x0) * math.cos(math.radians((y0 + y1) / 2)), y1 - y0) * 111.2
    return total


def join_lines(lines: list[list]) -> list[list]:
    """Join lines whose endpoints touch (end of one == start of another), keeping direction."""
    lines = [list(line) for line in lines]
    merged = True
    while merged:
        merged = False
        starts = {}
        for i, line in enumerate(lines):
            starts.setdefault(line[0], i)
        for i, line in enumerate(lines):
            j = starts.get(line[-1])
            if j is not None and j != i and lines[j] is not None and lines[i] is not None:
                lines[i] = line + lines[j][1:]
                lines[j] = None
                merged = True
                break
        lines = [line for line in lines if line is not None]
    return lines


def clip_line(line: list, comunas: Comunas) -> list[list]:
    """Runs of consecutive segments whose midpoint lies inside any commune polygon."""
    runs, cur = [], []
    for p, q in itertools.pairwise(line):
        if comunas.code_at((p[0] + q[0]) / 2, (p[1] + q[1]) / 2):
            cur = cur or [p]
            cur.append(q)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


# --- downloads --------------------------------------------------------------------------------


def get(
    url: str,
    *,
    ua: str = USER_AGENT,
    data: dict | None = None,
    referer: str | None = None,
    timeout: int = 300,
) -> bytes:
    headers = {"User-Agent": ua}
    if referer:
        headers["Referer"] = referer
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    with urllib.request.urlopen(
        urllib.request.Request(url, data=body, headers=headers), timeout=timeout
    ) as resp:
        return resp.read()


def cached(url: str, path: Path, manifest: dict, fetch, **extra) -> bytes:
    """Cache `fetch()` at `path` and record URL, date and SHA-256 in the manifest."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetch())
        time.sleep(1.0)
    content = path.read_bytes()
    manifest[path.relative_to(ROOT).as_posix()] = {
        "url": url,
        "descargado": dt.date.fromtimestamp(path.stat().st_mtime).isoformat(),
        "sha256": hashlib.sha256(content).hexdigest(),
        **extra,
    }
    return content


def fetch_overpass(query: str) -> bytes:
    last = None
    for url in OVERPASS:
        for wait in (0, 20, 60, 120):
            time.sleep(wait)
            try:
                return get(url, data={"data": query}, timeout=300)
            except urllib.error.HTTPError as e:
                last = e
                if e.code not in (429, 502, 503, 504):
                    break
            except (urllib.error.URLError, TimeoutError) as e:
                last = e
    raise RuntimeError(f"Overpass unreachable: {last}")


def accent_pattern(name: str) -> str:
    """Case-insensitive Overpass regex for a name, tolerant to accents in the OSM tag."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    alt = {"a": "[aá]", "e": "[eé]", "i": "[ií]", "o": "[oó]", "u": "[uúü]", "n": "[nñ]"}
    return "".join(alt.get(c.lower(), re.escape(c) if c != " " else " ") for c in plain)


def overpass_query(stream_names: list[str]) -> str:
    s, w, n, e = BBOX
    box = f"({s},{w},{n},{e})"
    streams = "|".join(accent_pattern(x) for x in sorted(set(stream_names)))
    return (
        f'[out:json][timeout:240];\n(\n  way["waterway"="river"]{box};\n'
        f'  way["waterway"="stream"]["name"~"^({streams})$",i]{box};\n);\nout geom;'
    )


# --- streamflow -------------------------------------------------------------------------------


def read_stations(raw: bytes) -> dict[str, dict]:
    rows = csv.DictReader(io.StringIO(raw.decode("latin-1")))
    return {r["codigo_estacion"]: r for r in rows}


def read_monthly(raw: bytes) -> dict[str, dict[tuple[int, int], float]]:
    """{station: {(year, month): m3/s}} from the wide CR2 table (missing = -9999)."""
    lines = raw.decode("latin-1").splitlines()
    codes = lines[0].split(",")[1:]
    series: dict[str, dict] = {c: {} for c in codes}
    for line in lines:
        head, _, rest = line.partition(",")
        if not re.fullmatch(r"\d{4}-\d{2}", head):
            continue
        y, m = int(head[:4]), int(head[5:])
        if y < PERIOD[0] or y > PERIOD[1]:
            continue
        for code, cell in zip(codes, rest.split(",")):
            if cell and float(cell) != MISSING:
                series[code][(y, m)] = float(cell)
    return series


def select_stations(stations: dict, series: dict, comunas: Comunas) -> list[dict]:
    kept = []
    for code, st in stations.items():
        if clave(st["nombre"].split(" ", 1)[0]) not in ("rio", "estero", "quebrada"):
            continue
        lon, lat = float(st["longitud"]), float(st["latitud"])
        comuna = comunas.code_at(lon, lat)
        if comuna is None:
            continue
        agg = aggregate(series[code])
        if agg["valid_years"] < MIN_YEARS or agg["valid_years_drought"] < MIN_YEARS_DROUGHT:
            continue
        kept.append(
            {
                "codigo": code,
                "nombre": re.sub(r"\bRio\b", "Río", st["nombre"]),
                "rio": rio_name(st["nombre"]),
                "lon": lon,
                "lat": lat,
                "altitud": int(float(st["altura"])),
                "comuna": comuna,
                "subcuenca": st["nombre_sub_cuenca"],
                "agg": agg,
            }
        )
    kept.sort(key=lambda s: -s["agg"]["medio"])
    return kept


def station_json(s: dict) -> dict:
    a = s["agg"]
    return {
        "codigo": s["codigo"],
        "nombre": s["nombre"],
        "rio": s["rio"],
        "lon": s["lon"],
        "lat": s["lat"],
        "altitud": s["altitud"],
        "comuna": s["comuna"],
        "subcuenca": s["subcuenca"],
        "anual": [r2(a["annual"].get(y)) for y in range(PERIOD[0], PERIOD[1] + 1)],
        "regimen": [r2(v) for v in a["regime"]],
        "medio": r2(a["medio"]),
        "base": r2(a["base"]),
        "sequia": r2(a["sequia"]),
        "cambio": a["cambio"],
        "cv": a["cv"],
    }


# --- rivers -----------------------------------------------------------------------------------


def build_rivers(osm: dict, stations: list[dict], comunas: Comunas) -> list[dict]:
    groups: dict[tuple, list] = {}
    unnamed = []
    for el in osm["elements"]:
        if el.get("type") != "way" or len(el.get("geometry", [])) < 2:
            continue
        line = [(g["lon"], g["lat"]) for g in el["geometry"]]
        name = el.get("tags", {}).get("name")
        clase = "stream" if el["tags"].get("waterway") == "stream" else "river"
        if name:
            groups.setdefault((name, clase), []).append(line)
        else:
            unnamed.append((None, clase, line))
    items = [(n, c, line) for (n, c), ls in groups.items() for line in join_lines(ls)] + unnamed

    best: dict[str, dict] = {}
    for s in stations:  # stations are sorted by medio, so the first one per key wins
        best.setdefault(river_key(s["rio"]), s)
    feats = []
    for name, clase, line in items:
        for run in clip_line(line, comunas):
            pts = dp_simplify(run, SIMPLIFY_DEG)
            pts = [(round(x, 4), round(y, 4)) for x, y in pts]
            pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
            if len(pts) < 2 or (name is None and length_km(pts) < MIN_UNNAMED_KM):
                continue
            st = best.get(river_key(name)) if name else None
            feats.append(
                {
                    "type": "Feature",
                    "properties": {
                        "nombre": name,
                        "clase": clase,
                        "estacion": st["codigo"] if st else None,
                    },
                    "geometry": {"type": "LineString", "coordinates": [list(p) for p in pts]},
                }
            )
    return feats


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    today = dt.date.today().isoformat()

    page = cached(
        PAGE, RAW / "cr2_caudales_pagina.html", manifest, lambda: get(PAGE, ua=BROWSER_UA)
    ).decode("utf-8", "replace")
    links = sorted(set(re.findall(r'https?://[^"\'\s<>]*' + ZIP_MARK + r'[^"\'\s<>]*', page, re.IGNORECASE)))
    if len(links) != 1:
        raise SystemExit(f"Expected one {ZIP_MARK} link on the CR2 page, found {links}")
    link = links[0].replace("&#038;", "&").replace("&amp;", "&")
    raw_zip = cached(
        link,
        RAW / "cr2_qflxAmon_2018.zip",
        manifest,
        lambda: get(link, ua=BROWSER_UA, referer=PAGE),
    )
    zf = zipfile.ZipFile(io.BytesIO(raw_zip))
    stations = read_stations(zf.read("cr2_qflxAmon_2018/cr2_qflxAmon_2018_stations.txt"))
    series = read_monthly(zf.read("cr2_qflxAmon_2018/cr2_qflxAmon_2018.txt"))
    download_date = manifest["data/raw/dga/cr2_qflxAmon_2018.zip"]["descargado"]

    comunas = Comunas.load()
    kept = select_stations(stations, series, comunas)

    write_csv(
        OUT / "caudales_rm_mensual.csv",
        ["codigo_estacion", "anio", "mes", "caudal_m3s"],
        [[s["codigo"], y, m, v] for s in kept for (y, m), v in sorted(series[s["codigo"]].items())],
    )
    write_csv(
        OUT / "estaciones_caudal_rm.csv",
        [
            "codigo_estacion",
            "nombre",
            "rio",
            "latitud",
            "longitud",
            "altitud",
            "codigo_comuna",
            "subcuenca",
            "anios_validos",
            "medio_m3s",
            "cambio_pct",
        ],
        [
            [
                s["codigo"],
                s["nombre"],
                s["rio"],
                s["lat"],
                s["lon"],
                s["altitud"],
                s["comuna"],
                s["subcuenca"],
                s["agg"]["valid_years"],
                r2(s["agg"]["medio"]),
                s["agg"]["cambio"],
            ]
            for s in kept
        ],
    )
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(
        json.dumps(
            {
                "meta": {
                    "fuente": "Dirección General de Aguas (MOP), caudales medios mensuales "
                    "compilados por (CR)2",
                    "url": PAGE,
                    "licencia": "CC0",
                    "descarga": download_date,
                    "unidad": "m³/s",
                    "periodo": list(PERIOD),
                    "base": list(BASE),
                    "sequia": list(DROUGHT),
                },
                "estaciones": [station_json(s) for s in kept],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{len(kept)} stations kept of {len(stations)}")

    stream_names = sorted({s["rio"] for s in kept})
    query = overpass_query(stream_names)
    osm_status = "ok"
    try:
        raw_osm = cached(
            OVERPASS[0],
            RAW / "overpass_rios_rm.json",
            manifest,
            lambda: fetch_overpass(query),
            post={"data": query},
        )
        feats = build_rivers(json.loads(raw_osm), kept, comunas)
        RIOS_OUT.parent.mkdir(parents=True, exist_ok=True)
        RIOS_OUT.write_text(
            json.dumps(
                {"type": "FeatureCollection", "features": feats},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        with_st = sum(1 for f in feats if f["properties"]["estacion"])
        print(
            f"{len(feats)} river features, {with_st} with a station, "
            f"{RIOS_OUT.stat().st_size / 1024:.0f} KB"
        )
    except (RuntimeError, OSError) as exc:
        osm_status = f"failed: {exc}"
        print("Rivers skipped:", osm_status)

    path = OUT / "manifest.json"
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    current.setdefault("fuente", "Dirección General de Aguas")
    current.setdefault("archivos", {}).update(manifest)
    current["caudales_rm"] = {
        "fuente": "DGA vía (CR)2, caudales medios mensuales 2018 (CC0); OpenStreetMap vía "
        "Overpass (ODbL)",
        "fecha": today,
        "overpass": osm_status,
        "consulta_overpass": query,
    }
    path.write_text(json.dumps(current, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
