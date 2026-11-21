"""Construye data/emisiones/pm25_por_comuna_fuente.csv a partir de datos abiertos del RETC (MMA).

Fuentes (datosretc.mma.gob.cl, CKAN):
  - Emisiones al aire de fuentes difusas   -> leña (residencial urbana + rural) y "otras" (incendios, quemas)
  - Emisiones al aire de transporte en ruta -> transporte (escape + desgaste de neumáticos) y polvo (-> otras)
  - Emisiones al aire de fuentes puntuales  -> industria (establecimientos RUEA/RETC)

Solo Región Metropolitana, contaminante MP2,5 (primario), toneladas/año.
No se estima nada: si una fuente/año no trae comuna (transporte 2017 y 2024: solo "Gran Santiago"), no se escribe fila.

Uso (desde la raíz del repo):  .venv/Scripts/python datos/emisiones/build_emisiones.py [--no-download]
Los archivos descargados son datos no confiables: solo se leen con pandas, nunca se ejecutan.
"""
import argparse
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "emisiones"
OUT = ROOT / "data" / "emisiones" / "pm25_por_comuna_fuente.csv"
BASE = "https://datosretc.mma.gob.cl/dataset"
DS_DIF = f"{BASE}/6e214ccc-c73f-41b5-b7d6-c4d874b7401c/resource"
DS_TR = f"{BASE}/5607a220-9c27-4f0c-b0a0-094450f8d160/resource"
DS_FP = f"{BASE}/2733b0f0-428a-4594-afeb-17780c8d47c1/resource"

FILES = {
    "difusas_2017.csv": f"{DS_DIF}/7db000c3-dc82-4778-bb6d-953588030dba/download/ruea-efd-2017-ckan.csv",
    "difusas_2023.xlsx": f"{DS_DIF}/788d5d79-901e-41f5-9c67-b10e96d44488/download/efd-ckan-2023.xlsx",
    "difusas_2024.csv": f"{DS_DIF}/226b85df-8419-47a5-a834-40e51476ce6c/download/ruea-efd-2024-ckan.csv",
    "transporte_2017.csv": f"{DS_TR}/2a25ae1c-e258-4617-b4fd-6e1fb66572b1/download/ruea-tr-2017-ckan.csv",
    "transporte_2023.csv": f"{DS_TR}/55590aed-d079-43b0-8e2d-d9f27741e486/download/ruea-tr-2023-ckan.csv",
    "transporte_2024.csv": f"{DS_TR}/901174b2-5caf-411c-96f0-866fedf7f838/download/ruea-tr-2024-ckan_mejora.csv",
    "puntuales_2017.csv": f"{DS_FP}/c82279c0-acda-44de-9c0f-f1350e90fb9e/download/ruea-efp-2017-ckan.csv",
    "puntuales_2023.xlsx": f"{DS_FP}/d40cc934-4a51-4236-8109-1051b8cc8592/download/ckan_fp_2023_da.xlsx",
    "puntuales_2024.xlsx": f"{DS_FP}/b82ed4a8-ed64-493a-8159-563abf0bf5ad/download/ckan_fp_2024_da.xlsx",
}


def download(name, url, tries=12):
    """Descarga con verificación de Content-Length (el servidor devuelve 503 y trunca a veces)."""
    dest = RAW / name
    for attempt in range(tries):
        if attempt:
            time.sleep(8)
        try:
            r = requests.get(url, stream=True, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                r.close()
                continue
            expected = int(r.headers.get("Content-Length", -1))
            if dest.exists() and (expected < 0 or dest.stat().st_size == expected):
                r.close()
                return
            tmp = dest.with_suffix(dest.suffix + ".part")
            n = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    n += len(chunk)
            if expected >= 0 and n != expected:
                continue
            tmp.replace(dest)
            return
        except requests.RequestException:
            pass
    raise RuntimeError(f"no se pudo descargar completo: {name}")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return s.strip()


def num(series):
    if series.dtype == object or str(series.dtype).startswith("str"):
        return pd.to_numeric(series.astype(str).str.replace(",", ".", regex=False), errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def read_csv(name):
    p = RAW / name
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(p, sep=";", encoding=enc, dtype=str, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(name)


def fix_cols(df):
    # normaliza nombres de columna (año con encoding roto, mayúsculas)
    df.columns = [norm(c).replace("?", "n").replace("�", "n") for c in df.columns]
    return df


def is_rm(region):
    return region.map(norm).str.startswith("metropolitana")


def difusas(year):
    f = f"difusas_{year}.xlsx" if year == 2023 else f"difusas_{year}.csv"
    if f.endswith("xlsx"):
        df = pd.read_excel(RAW / f, dtype=str)
    else:
        df = read_csv(f)
    df = fix_cols(df)
    df = df[is_rm(df["region"]) & (df["contaminantes"].map(norm) == "mp2,5")].copy()
    df["t"] = num(df["cantidad_toneladas"])
    df["fuente"] = df["tipo_fuente"].map(lambda s: "lena" if "lena" in norm(s) else "otras")
    df["codigo_comuna"] = df["id_comuna"].astype(str).str.replace(r"\.0$", "", regex=True)
    out = df.groupby(["codigo_comuna", "comuna", "fuente"], as_index=False)["t"].sum()
    out["anio"] = year
    out["origen_dato"] = f"RETC fuentes difusas {year} ({f}); MP2,5; leña=urbana+rural; otras=incendios forestales/urbanos+quemas agrícolas"
    return out


def transporte(year):
    df = fix_cols(read_csv(f"transporte_{year}.csv"))
    if "comuna" not in df.columns:
        print(f"[aviso] transporte {year}: el archivo no trae comuna (solo ciudad 'Gran Santiago'); sin filas.", file=sys.stderr)
        return pd.DataFrame()
    df = df[is_rm(df["region"]) & (df["contaminantes"].map(norm) == "mp2,5")].copy()
    df["t"] = num(df["cantidad_toneladas"])
    df["fuente"] = df["tipo_emision"].map(lambda s: "otras" if "polvo" in norm(s) else "transporte")
    df["codigo_comuna"] = df["id_comuna"].astype(str).str.replace(r"\.0$", "", regex=True)
    out = df.groupby(["codigo_comuna", "comuna", "fuente"], as_index=False)["t"].sum()
    out["anio"] = year
    out["origen_dato"] = (
        f"RETC transporte en ruta {year} (transporte_{year}.csv); MP2,5; transporte=escape+desgaste neumáticos; "
        "otras=resuspensión 'polvo natural' de calles; solo comunas del Gran Santiago"
    )
    return out


def puntuales(year):
    f = f"puntuales_{year}.csv" if year == 2017 else f"puntuales_{year}.xlsx"
    if f.endswith("xlsx"):
        df = pd.read_excel(RAW / f, sheet_name="Data", dtype=str)
    else:
        df = read_csv(f)
    df = fix_cols(df)
    cont = df["contaminante" if "contaminante" in df.columns else "contaminantes"].map(norm)
    df = df[is_rm(df["region"]) & cont.isin(["pm2.5, primary", "mp2,5", "mp2.5"])].copy()
    if "emision_retc" in df.columns:
        df["t"] = num(df["emision_retc"])
        col = "emision_retc (validada MMA)"
    else:
        df["t"] = num(df["cantidad_toneladas"])
        col = "cantidad_toneladas"
        if "unidad" in df.columns and not df["unidad"].map(norm).str.startswith("ton").all():
            raise RuntimeError("unidades distintas de ton/año en puntuales " + str(year))
    ccol = "codigo_unico_territorial" if "codigo_unico_territorial" in df.columns else "id_comuna"
    df["codigo_comuna"] = df[ccol].astype(str).str.replace(r"\.0$", "", regex=True)
    df["fuente"] = "industria"
    out = df.groupby(["codigo_comuna", "comuna", "fuente"], as_index=False)["t"].sum()
    mx = df.groupby("codigo_comuna")["t"].max()
    out["anio"] = year
    out["origen_dato"] = f"RETC fuentes puntuales {year} ({f}); PM2.5 primario; columna {col}; todos los establecimientos declarados"
    big = out["codigo_comuna"].map(mx) > 100
    out.loc[big, "origen_dato"] += (
        "; AVISO: incluye una fuente individual >100 t/año de PM2.5 (valor del dato publicado, probable error de unidad o de declaración; no corregido)"
    )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not a.no_download:
        for n, u in FILES.items():
            download(n, u)
    parts = []
    for y in (2017, 2023, 2024):
        for fn in (difusas, transporte, puntuales):
            d = fn(y)
            if len(d):
                parts.append(d)
    res = pd.concat(parts, ignore_index=True)
    # una fila por (año, comuna, fuente): 'otras' junta difusas (incendios, quemas) y polvo de calles
    names = res.groupby("codigo_comuna")["comuna"].agg(lambda x: x.mode().iloc[0])
    res["comuna"] = res["codigo_comuna"].map(names)
    res = res.groupby(["anio", "codigo_comuna", "comuna", "fuente"], as_index=False).agg(
        t=("t", "sum"), origen_dato=("origen_dato", " | ".join)
    )
    res = res.rename(columns={"t": "toneladas_anio"})
    res["toneladas_anio"] = res["toneladas_anio"].round(4)
    res = res[["anio", "comuna", "codigo_comuna", "fuente", "toneladas_anio", "origen_dato"]]
    res = res.sort_values(["anio", "codigo_comuna", "fuente"])
    res.to_csv(OUT, index=False, encoding="utf-8")
    print(res.groupby(["anio", "fuente"]).agg(comunas=("comuna", "nunique"), t=("toneladas_anio", "sum")))
    print("escrito", OUT)


if __name__ == "__main__":
    main()
