"""Filtra las comunas de la Región Metropolitana (CUT_REG == "13") desde la
División Político Administrativa 2023 (SUBDERE / SNIT) y genera un GeoJSON
liviano para mapas web.

Fuente: Limite_DPA_03082023.rar (https://ide.subdere.gov.cl/descargas/SHP/Limite_DPA_03082023.rar)
Sistema de referencia del shapefile: GCS SIRGAS-Chile (grados, elipsoide GRS80).
Se trata como WGS84: la diferencia es del orden de 1 m, irrelevante para un mapa web.

Uso (desde la raíz del repo, con el Python del venv):
  1. Extraer el .rar en una carpeta nueva y vacía (p. ej. con tar.exe de Windows):
       tar -xf data/raw/geo/Limite_DPA_03082023.rar -C <carpeta_vacia>
  2. Ejecutar (siempre con -I, el insumo es un archivo descargado):
       python -I datos/geo/build_comunas.py --shp <carpeta_vacia>/DPA_2023/COMUNAS/COMUNAS_v1.shp \
           --out viz/public/geo/comunas_rm.geojson
"""

import argparse
import json
import os
import sys

import shapefile  # pyshp
import shapely
from shapely.geometry import mapping, shape
from shapely.validation import make_valid

REGION_RM = "13"
GRID = 1e-5          # ~1.1 m; redondeo a 5 decimales
SIMPLIFY_TOL = 0.0001  # grados (~11 m); preserva topología
EXPECTED = 52


def clean_text(value):
    return " ".join((value or "").split())


def build(shp_path):
    reader = shapefile.Reader(shp_path, encoding="utf-8")
    features = []
    for sr in reader.iterShapeRecords():
        rec = sr.record.as_dict()
        if str(rec["CUT_REG"]).strip() != REGION_RM:
            continue
        geom = shape(sr.shape.__geo_interface__)
        if not geom.is_valid:
            geom = make_valid(geom)
        geom = shapely.set_precision(geom, GRID)
        geom = geom.simplify(SIMPLIFY_TOL, preserve_topology=True)
        geom = shapely.set_precision(geom, GRID)
        if geom.geom_type == "GeometryCollection":
            polys = [g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
            geom = shapely.union_all(polys) if polys else geom
        features.append({
            "type": "Feature",
            "properties": {
                "codigo": str(rec["CUT_COM"]).strip().zfill(5),
                "nombre": clean_text(rec["COMUNA"]),
                "provincia": clean_text(rec["PROVINCIA"]),
            },
            "geometry": round_coords(mapping(geom)),
        })
    features.sort(key=lambda f: f["properties"]["codigo"])
    return {"type": "FeatureCollection", "features": features}


def round_coords(obj):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(obj[0]), 5), round(float(obj[1]), 5)]
        return [round_coords(x) for x in obj]
    return obj


def check(fc):
    feats = fc["features"]
    assert len(feats) == EXPECTED, f"se esperaban {EXPECTED} comunas, hay {len(feats)}"
    codes = [f["properties"]["codigo"] for f in feats]
    assert len(set(codes)) == len(codes), "codigos duplicados"
    assert all(c.startswith(REGION_RM) and len(c) == 5 for c in codes)
    for f in feats:
        g = f["geometry"]
        assert g["type"] in ("Polygon", "MultiPolygon"), g["type"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shp", required=True, help="Ruta a COMUNAS_v1.shp extraído")
    ap.add_argument("--out", required=True, help="GeoJSON de salida")
    args = ap.parse_args()

    fc = build(args.shp)
    check(fc)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fc, fh, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(args.out)
    print(f"{len(fc['features'])} comunas -> {args.out} ({size / 1024:.1f} KB)")


if __name__ == "__main__":
    sys.exit(main())
