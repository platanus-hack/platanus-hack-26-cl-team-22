"""Construye data/comunas_rm.csv (52 comunas de la Región Metropolitana).

Columnas y origen:
  codigo_comuna, provincia, poblacion_2017 : INE, Censo 2017, tabla comunal (Geodatos Abiertos INE, ArcGIS Hub)
      https://geoine-ine-chile.opendata.arcgis.com/datasets/1c64fcb18f5a41e088b25ef9f42b58d7_0  (T_POB = población censada 2017)
  poblacion_2024 : INE, Censo 2024, base de microdatos de personas (viv_hog_per_censo2024.zip, 4-dic-2025);
      se cuentan filas (personas) por código de comuna. Requiere pyarrow.
  lat, lon : Wikidata P625 (coordenada del ítem comuna; es un punto representativo, normalmente el centro
      urbano/cabecera, NO un centroide areal calculado del polígono). Consulta SPARQL guardada en data/raw/comunas/.

Uso: .venv/Scripts/python datos/comunas/build_comunas.py   (los archivos de data/raw ya deben existir; ver README del script en docs)
"""
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_INE = ROOT / "data" / "raw" / "ine"
WD = ROOT / "data" / "raw" / "comunas" / "wikidata_comunas_rm.csv"
OUT = ROOT / "data" / "comunas_rm.csv"
ZIP24 = RAW_INE / "viv_hog_per_censo2024.zip"
PQ24 = RAW_INE / "personas_censo2024.parquet"


def norm(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def pop2024():
    import pyarrow.parquet as pq

    if not PQ24.exists():
        with zipfile.ZipFile(ZIP24) as z:
            z.extract("personas_censo2024.parquet", RAW_INE)
    df = pq.read_table(PQ24, columns=["region", "comuna"]).to_pandas()
    df = df[df["region"] == 13]
    return df.groupby("comuna").size().rename("poblacion_2024")


def main():
    ine = pd.read_csv(RAW_INE / "censo2017_comuna.csv", encoding="utf-8-sig")
    ine = ine[ine["REGION"] == 13].copy()
    ine["key"] = ine["NOM_COMUNA"].map(norm)
    ine["comuna"] = ine["NOM_COMUNA"].str.title().str.replace(" De ", " de ", regex=False)
    ine["provincia"] = ine["NOM_PROVIN"].str.title()
    ine = ine.rename(columns={"COMUNA": "codigo_comuna", "T_POB": "poblacion_2017"})
    assert len(ine) == 52, len(ine)

    wd = pd.read_csv(WD).drop_duplicates("c")
    m = wd["coord"].str.extract(r"Point\((-?[\d.]+) (-?[\d.]+)\)")
    wd["lon"] = m[0].astype(float)
    wd["lat"] = m[1].astype(float)
    wd["key"] = wd["lab"].map(norm)
    wd = wd[["key", "lat", "lon"]]

    out = ine.merge(wd, on="key", how="left")
    out = out.merge(pop2024(), left_on="codigo_comuna", right_index=True, how="left")
    out = out[["codigo_comuna", "comuna", "provincia", "lat", "lon", "poblacion_2017", "poblacion_2024"]]
    out = out.sort_values("codigo_comuna")
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(out.isna().sum()); print(out[["poblacion_2017", "poblacion_2024"]].sum()); print("escrito", OUT)


if __name__ == "__main__":
    main()
