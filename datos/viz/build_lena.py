"""Construye viz/public/datos/lena.json: emisiones de MP2,5 por leña (RETC 2023) por comuna y zona.

Entradas (ya en el repo, no se descarga nada):
  - data/emisiones/pm25_por_comuna_fuente.csv  (año 2023, fuente "lena", toneladas/año)
  - data/comunas_rm.csv                        (nombre, provincia y población 2024 de las 52 comunas)

Zonas del D.S. 31/2016 (PPDA de la RM), art. 73, tal como están en docs/politicas-aire.md:
  - Zona B = las 18 comunas listadas abajo.
  - Zona A = las otras 34 (provincia de Santiago, San Bernardo y Puente Alto).

Una comuna sin fila de leña en 2023 queda con toneladas = null ("sin dato"); nunca se escribe cero.

Uso (desde la raíz del repo):  .venv/Scripts/python -I datos/viz/build_lena.py
"""
import csv
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EMISIONES = ROOT / "data" / "emisiones" / "pm25_por_comuna_fuente.csv"
COMUNAS = ROOT / "data" / "comunas_rm.csv"
OUT = ROOT / "viz" / "public" / "datos" / "lena.json"
ANIO = 2023

ZONA_B = [
    "Alhué", "Buin", "Calera de Tango", "Colina", "Curacaví", "El Monte", "Isla de Maipo",
    "Lampa", "María Pinto", "Melipilla", "Padre Hurtado", "Paine", "Peñaflor", "Pirque",
    "San Pedro", "San José de Maipo", "Talagante", "Tiltil",
]


def clave(nombre: str) -> str:
    """Minúsculas, sin tildes ni espacios: para comparar nombres de comuna."""
    s = unicodedata.normalize("NFD", nombre)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return "".join(c for c in s if c.isalnum())


def main() -> int:
    with COMUNAS.open(encoding="utf-8") as f:
        comunas = list(csv.DictReader(f))
    zona_b = {clave(n) for n in ZONA_B}
    encontradas = {clave(c["comuna"]) for c in comunas} & zona_b
    if len(encontradas) != len(ZONA_B) or len(comunas) != 52:
        faltan = sorted(zona_b - encontradas)
        print(f"Error: {len(comunas)} comunas, zona B emparejada {len(encontradas)}/18; faltan {faltan}")
        return 1

    toneladas: dict[str, float] = {}
    with EMISIONES.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["anio"] == str(ANIO) and r["fuente"] == "lena":
                cod = r["codigo_comuna"].strip()
                toneladas[cod] = toneladas.get(cod, 0.0) + float(r["toneladas_anio"])

    filas = []
    tot = {"A": 0.0, "B": 0.0}
    pob = {"A": 0, "B": 0}
    for c in comunas:
        cod = c["codigo_comuna"].strip()
        zona = "B" if clave(c["comuna"]) in zona_b else "A"
        t = toneladas.get(cod)
        p = int(c["poblacion_2024"])
        pob[zona] += p
        if t is not None:
            tot[zona] += t
        filas.append({
            "codigo": cod,
            "nombre": c["comuna"],
            "zona": zona,
            "toneladas": round(t, 3) if t is not None else None,
            "poblacion": p,
        })

    n_a = sum(1 for x in filas if x["zona"] == "A")
    n_b = sum(1 for x in filas if x["zona"] == "B")
    total = tot["A"] + tot["B"]
    pob_total = pob["A"] + pob["B"]
    sin_dato = [x["nombre"] for x in filas if x["toneladas"] is None]
    salida = {
        "meta": {
            "anio": ANIO,
            "fuente": "RETC 2023, fuentes difusas (MMA): MP2,5 de leña residencial urbana y rural",
            "zonas": "D.S. 31/2016 (PPDA RM), art. 73",
            "poblacion": "Población 2024 (data/comunas_rm.csv)",
            "unidad": "t/año",
            "generado_por": "datos/viz/build_lena.py",
            "es_real": True,
        },
        "zonas": {
            z: {
                "comunas": n,
                "toneladas": round(tot[z], 1),
                "parte_emisiones": round(tot[z] / total, 4),
                "poblacion": pob[z],
                "parte_poblacion": round(pob[z] / pob_total, 4),
            }
            for z, n in (("A", n_a), ("B", n_b))
        },
        "comunas": filas,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"Zona A: {n_a} comunas, {tot['A']:,.0f} t; Zona B: {n_b} comunas, {tot['B']:,.0f} t")
    print(f"Total: {total:,.0f} t. Parte de la Zona B: {tot['B'] / total:.1%}")
    print(f"Población Zona B: {pob['B'] / pob_total:.1%}. Sin dato: {', '.join(sin_dato) or 'ninguna'}")
    print(f"Escrito {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
