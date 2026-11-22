"""Construye viz/public/datos/inversion.json: cuatro indicadores por comuna para quien quiere invertir.

Entradas (ya en el repo, no se descarga nada):
  - data/comunas_rm.csv                   (las 52 comunas)
  - data/dga/decretos_escasez_rm.csv      (decretos de escasez hídrica, DGA)
  - data/arclim/componentes_comuna.csv    (riesgos climáticos por comuna, ARClim)
  - data/energia/subestaciones_rm.csv     (subestaciones eléctricas, Coordinador Eléctrico Nacional)
  - data/seia/proyectos_rm.csv            (proyectos del SEIA, SEA)

Reglas (un valor ausente es null, nunca 0, salvo donde 0 es el valor real):
  - escasez_hidrica: años distintos de 2008 a 2023 con al menos un decreto vigente. Un decreto cubre
    desde el año de fecha_decreto (o de la columna anio si falta) hasta el año de fecha_caducidad
    (o solo su año de inicio si falta). Sin decretos: 0.
  - sequia_futura: columna amen_sequia_combinada_fut de ARClim (amenaza de sequía hidrológica combinada
    en el futuro 2035-2065, escala 0 a 1 normalizada por ARClim). Celda vacía: null.
  - red_electrica: suma de capacidad_mva de subestaciones EN_OPERACION. Sin subestaciones: 0;
    con subestaciones pero ninguna con capacidad: null.
  - inversion_evaluada: proyectos "Aprobado" con fecha_presentacion desde 2015-01-01; uno que
    nombra varias comunas (separadas por ";") cuenta una vez en cada una. No se suma inversion_musd.

Uso (desde la raíz del repo):  python -I datos/viz/build_inversion.py
"""

import csv
import json
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMUNAS = ROOT / "data" / "comunas_rm.csv"
DECRETOS = ROOT / "data" / "dga" / "decretos_escasez_rm.csv"
ARCLIM = ROOT / "data" / "arclim" / "componentes_comuna.csv"
SUBESTACIONES = ROOT / "data" / "energia" / "subestaciones_rm.csv"
SEIA = ROOT / "data" / "seia" / "proyectos_rm.csv"
OUT = ROOT / "viz" / "public" / "datos" / "inversion.json"

ANIO_DESDE, ANIO_HASTA = 2008, 2023
SEIA_DESDE = "2015-01-01"
COLUMNA_SEQUIA = "amen_sequia_combinada_fut"


def leer(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def anios_con_decreto(
    decretos: list[tuple[str, str, str]], desde: int = ANIO_DESDE, hasta: int = ANIO_HASTA
) -> int:
    """Años distintos en [desde, hasta] cubiertos por algún decreto (anio, fecha_decreto, fecha_caducidad)."""
    cubiertos: set[int] = set()
    for anio, fecha_decreto, fecha_caducidad in decretos:
        inicio = int(fecha_decreto[:4]) if fecha_decreto else int(anio)
        fin = int(fecha_caducidad[:4]) if fecha_caducidad else inicio
        cubiertos.update(range(max(inicio, desde), min(fin, hasta) + 1))
    return len(cubiertos)


def capacidad_operando(filas: list[dict]) -> float | None:
    """Suma de MVA en operación; 0 si no hay subestaciones, None si ninguna trae capacidad."""
    operando = [f for f in filas if f["estado"] == "EN_OPERACION"]
    if not operando:
        return 0.0
    mva = [float(f["capacidad_mva"]) for f in operando if f["capacidad_mva"]]
    return sum(mva) if mva else None


def proyectos_aprobados(filas: list[dict], desde: str = SEIA_DESDE) -> dict[str, int]:
    """Proyectos aprobados desde `desde` por comuna; los multicomuna cuentan una vez en cada una."""
    cuenta: dict[str, int] = {}
    for f in filas:
        if (
            f["estado"] != "Aprobado"
            or not f["fecha_presentacion"]
            or f["fecha_presentacion"] < desde
        ):
            continue
        for cod in {c.strip() for c in f["codigos_comuna"].split(";") if c.strip()}:
            cuenta[cod] = cuenta.get(cod, 0) + 1
    return cuenta


def valores_por_comuna(codigos: list[str]) -> dict[str, dict]:
    por_decreto: dict[str, list] = {}
    for r in leer(DECRETOS):
        por_decreto.setdefault(r["codigo_comuna"].strip(), []).append(
            (r["anio"], r["fecha_decreto"], r["fecha_caducidad"])
        )
    sequia = {r["codigo_comuna"].strip(): r[COLUMNA_SEQUIA] for r in leer(ARCLIM)}
    subs: dict[str, list] = {}
    for r in leer(SUBESTACIONES):
        subs.setdefault(r["codigo_comuna"].strip(), []).append(r)
    aprobados = proyectos_aprobados(leer(SEIA))

    out = {}
    for cod in codigos:
        s = sequia.get(cod, "")
        mva = capacidad_operando(subs.get(cod, []))
        out[cod] = {
            "escasez_hidrica": anios_con_decreto(por_decreto.get(cod, [])),
            "sequia_futura": round(float(s), 2) if s else None,
            "red_electrica": round(mva, 2) if mva is not None else None,
            "inversion_evaluada": aprobados.get(cod, 0),
        }
    return out


def main() -> int:
    nombres = {r["codigo_comuna"].strip(): r["comuna"] for r in leer(COMUNAS)}
    codigos = sorted(nombres)
    if len(codigos) != 52:
        print(f"Error: {len(codigos)} comunas en {COMUNAS.name}, se esperaban 52")
        return 1
    valores = valores_por_comuna(codigos)

    anio_seia = max(r["fecha_presentacion"] for r in leer(SEIA))[:4]
    indicadores = [
        {
            "id": "escasez_hidrica",
            "nombre": "Escasez hídrica",
            "que": "Años con decreto de escasez hídrica, 2008–2023",
            "unidad": "años",
            "mejor": "menor",
            "fuente": "DGA (MOP)",
            "periodo": "2008–2023",
        },
        {
            "id": "sequia_futura",
            "nombre": "Sequía futura",
            "que": "Amenaza de sequía hidrológica combinada proyectada (escala 0 a 1 de ARClim); "
            "solo 9 comunas tienen dato",
            "unidad": "índice 0–1",
            "mejor": "menor",
            "fuente": "ARClim (MMA)",
            "periodo": "2035–2065",
        },
        {
            "id": "red_electrica",
            "nombre": "Red eléctrica",
            "que": "Capacidad de subestaciones en operación",
            "unidad": "MVA",
            "mejor": "mayor",
            "fuente": "Coordinador Eléctrico Nacional (Infotécnica)",
            "periodo": "2026-11-21 (foto)",
        },
        {
            "id": "inversion_evaluada",
            "nombre": "Inversión evaluada",
            "que": "Proyectos aprobados en evaluación ambiental desde 2015",
            "unidad": "proyectos",
            "mejor": "mayor",
            "fuente": "SEIA (SEA)",
            "periodo": f"2015–{anio_seia}",
        },
    ]
    salida = {
        "meta": {
            "generado": date.today().isoformat(),
            "comando": "python -I datos/viz/build_inversion.py",
        },
        "indicadores": indicadores,
        "comunas": [{"codigo": c, "valores": valores[c]} for c in codigos],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(salida, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )

    for ind in indicadores:
        k = ind["id"]
        con = sorted((v[k], nombres[c]) for c, v in valores.items() if v[k] is not None)
        nums = [x for x, _ in con]
        orden = con if ind["mejor"] == "menor" else con[::-1]
        print(
            f"{k}: {len(con)} con dato, {52 - len(con)} null; min {nums[0]}, "
            f"mediana {statistics.median(nums)}, max {nums[-1]}"
        )
        print("  mejores:", orden[:3], " peores:", orden[::-1][:3])
    print(f"Escrito {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
