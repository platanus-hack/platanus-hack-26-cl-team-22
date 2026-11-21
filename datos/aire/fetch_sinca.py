#!/usr/bin/env python
"""Descarga PM2.5 diario de las estaciones SINCA/MACAM de la Region Metropolitana.

Uso (desde la raiz del repo):  .venv/Scripts/python datos/aire/fetch_sinca.py
Las respuestas crudas se cachean en data/raw/sinca/; borrar el archivo para reintentar.
Salidas: data/aire/{pm25_diario,estaciones,pm25_mensual,pm25_anual}.csv
No interpola ni inventa valores: dias sin dato quedan ausentes.
"""
import calendar
import html
import io
import math
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "sinca"
OUT = ROOT / "data" / "aire"
BASE = "https://sinca.mma.gob.cl"
REGION_URL = BASE + "/index.php/region/index/id/M"
# "to" es exclusivo: 250101 para incluir 2024-12-31.
CSV_URL = (BASE + "/cgi-bin/APUB-MMA/apub.tsindico2.cgi?outtype=xcl"
           "&macro=./RM/{code}/Cal/PM25//PM25.diario.diario.ic&from=170101&to=250101"
           "&path=/usr/airviro/data/CONAMA/&lang=esp&rsrc=&macropath=")
HEADERS = {"User-Agent": "Mozilla/5.0 (research script; hackathon air-quality data)"}
SLEEP = 1.5
START, END = pd.Timestamp("2017-01-01"), pd.Timestamp("2024-12-31")
MIN_FRAC = 0.75


def get(url, dest: Path):
    """GET con cache en disco, reintentos y pausa. Devuelve los bytes."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for wait in (0, 5, 15, 45):
        time.sleep(wait or SLEEP)
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code == 200 and r.content:
                dest.write_bytes(r.content)
                return r.content
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = repr(e)
    sys.exit(f"No se pudo descargar {url}: {last}")


def dec(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("latin-1")


def utm19s_to_latlon(e, n):
    """UTM huso 19 sur -> lat/lon (WGS84; SINCA no declara datum, asumido WGS84/SIRGAS)."""
    a, f = 6378137.0, 1 / 298.257223563
    k0 = 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x, y = e - 500000.0, n - 10000000.0
    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p = (mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
         + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
         + (151 * e1**3 / 96) * math.sin(6 * mu)
         + (1097 * e1**4 / 512) * math.sin(8 * mu))
    s, c, t = math.sin(p), math.cos(p), math.tan(p)
    n1 = a / math.sqrt(1 - e2 * s**2)
    t1, c1 = t**2, ep2 * c**2
    r1 = a * (1 - e2) / (1 - e2 * s**2) ** 1.5
    d = x / (n1 * k0)
    lat = p - (n1 * t / r1) * (d**2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ep2) * d**4 / 24
                               + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ep2 - 3 * c1**2) * d**6 / 720)
    lon0 = math.radians(-69)
    lon = lon0 + (d - (1 + 2 * t1 + c1) * d**3 / 6
                  + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ep2 + 24 * t1**2) * d**5 / 120) / c
    return math.degrees(lat), math.degrees(lon)


def discover():
    """Lee la tabla regional y la ficha de cada estacion. Devuelve lista de dicts."""
    page = dec(get(REGION_URL, RAW / "pages" / "region_M.html"))
    ids = sorted(set(re.findall(r"/index\.php/estacion/index/id/(\d+)", page)), key=int)
    out = []
    for sid in ids:
        h = dec(get(f"{BASE}/index.php/estacion/index/id/{sid}", RAW / "pages" / f"estacion_{sid}.html"))
        m = re.search(r"macropath=\./RM/(D\d+)/Cal/PM25&amp;macro=PM25\.diario", h)
        if not m:
            print(f"  estacion {sid}: no mide PM2.5, se omite")
            continue
        name = html.unescape(re.search(r"header=([^&]+)&", h).group(1)).strip()
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))
        com = re.search(r"Comuna ([^\d]+?) Coordenadas UTM (\d+) E (\d+) N", text)
        if not com:
            sys.exit(f"Ficha {sid}: no se pudo leer comuna/UTM")
        lat, lon = utm19s_to_latlon(int(com.group(2)), int(com.group(3)))
        out.append({"sinca_id": sid, "codigo": m.group(1), "estacion": name, "comuna": com.group(1).strip(),
                        "lat": round(lat, 5), "lon": round(lon, 5)})
    return out


def parse_csv(b: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(dec(b)), sep=";", dtype=str, index_col=False)
    df = df.iloc[:, :5]
    df.columns = ["fecha", "hora", "validado", "preliminar", "no_validado"]
    df["fecha"] = pd.to_datetime(df["fecha"], format="%y%m%d", errors="coerce")
    rows = []
    for est in ("validado", "preliminar", "no_validado"):
        v = pd.to_numeric(df[est].str.replace(",", "."), errors="coerce")
        rows.append(pd.DataFrame({"fecha": df["fecha"], "pm25": v, "estado": est}))
    long = pd.concat(rows).dropna()
    # prioridad validado > preliminar > no_validado, un registro por dia
    long["p"] = long["estado"].map({"validado": 0, "preliminar": 1, "no_validado": 2})
    long = long.sort_values(["fecha", "p"]).drop_duplicates("fecha").drop(columns="p")
    return long[(long.fecha >= START) & (long.fecha <= END)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stations = discover()
    frames = []
    for s in stations:
        slug = re.sub(r"[^a-z0-9]+", "_", s["estacion"].lower()).strip("_")
        raw = get(CSV_URL.format(code=s["codigo"]), RAW / f"{s['codigo']}_{slug}.csv")
        d = parse_csv(raw)
        d["estacion_id"], d["estacion"] = s["codigo"], s["estacion"]
        frames.append(d)
        print(f"  {s['codigo']} {s['estacion']:28s} {len(d):5d} dias")
    daily = pd.concat(frames)[["fecha", "estacion_id", "estacion", "pm25", "estado"]]
    daily = daily.sort_values(["estacion_id", "fecha"])
    d_out = daily.copy()
    d_out["fecha"] = d_out["fecha"].dt.strftime("%Y-%m-%d")
    d_out.to_csv(OUT / "pm25_diario.csv", index=False)

    total = (END - START).days + 1
    est_rows = []
    for s in stations:
        d = daily[daily.estacion_id == s["codigo"]]
        est_rows.append({
            "estacion_id": s["codigo"], "estacion": s["estacion"], "comuna": s["comuna"], "lat": s["lat"], "lon": s["lon"],
            "primera_fecha": d.fecha.min().strftime("%Y-%m-%d") if len(d) else "",
            "ultima_fecha": d.fecha.max().strftime("%Y-%m-%d") if len(d) else "",
            "pct_dias_con_dato_2017_2024": round(100 * len(d) / total, 1)})
    pd.DataFrame(est_rows).to_csv(OUT / "estaciones.csv", index=False)

    daily["anio"], daily["mes"] = daily.fecha.dt.year, daily.fecha.dt.month
    mrows = []
    for (eid, est, y, m), g in daily.groupby(["estacion_id", "estacion", "anio", "mes"]):
        dim = calendar.monthrange(y, m)[1]
        n = len(g)
        mrows.append({"estacion_id": eid, "estacion": est, "anio": y, "mes": m, "dias_validos": n, "dias_mes": dim,
                          "pm25_media": round(g.pm25.mean(), 2) if n / dim >= MIN_FRAC else None})
    pd.DataFrame(mrows).to_csv(OUT / "pm25_mensual.csv", index=False)

    arows = []
    for (eid, est, y), g in daily.groupby(["estacion_id", "estacion", "anio"]):
        diy = 366 if calendar.isleap(y) else 365
        n = len(g)
        inv = g[g.mes.between(5, 8)]
        nw = len(inv)  # mayo-agosto = 123 dias
        arows.append({
            "estacion_id": eid, "estacion": est, "anio": y, "dias_validos": n, "dias_anio": diy,
            "pm25_media": round(g.pm25.mean(), 2) if n / diy >= MIN_FRAC else None,
            "dias_validos_invierno": nw, "dias_invierno": 123,
            "pm25_media_invierno": round(inv.pm25.mean(), 2) if nw / 123 >= MIN_FRAC else None})
    pd.DataFrame(arows).to_csv(OUT / "pm25_anual.csv", index=False)
    print("Listo.")


if __name__ == "__main__":
    main()
