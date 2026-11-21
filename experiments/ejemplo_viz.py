"""Genera viz/ejemplo/simulacion.json: datos DE EJEMPLO para construir la interfaz.

No es un resultado del modelo. La línea base (PM2,5 de invierno 2024 por
estación) es real y viene de data/aire/; las trayectorias, bandas, políticas,
credibilidades y flujos son inventados con una semilla fija, solo para que la
interfaz tenga algo con la forma del contrato (docs/plan-comunas.md).

Uso:  python -m experiments.ejemplo_viz
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
F_ESTACIONES = RAIZ / "data" / "aire" / "estaciones.csv"
F_ANUAL = RAIZ / "data" / "aire" / "pm25_anual.csv"
F_SALIDA = RAIZ / "viz" / "ejemplo" / "simulacion.json"

ANIO_BASE = 2024
ANIOS = list(range(2026, 2037))
SEMILLA = 22

POLITICAS = [
    {"id": "ppda-lena", "nombre": "Restricción de calefacción a leña", "nivel": "regional",
     "fuente": "lena", "comunas": "todas", "credibilidad": {"p10": 0.45, "media": 0.6, "p90": 0.75}},
    {"id": "ppda-transporte", "nombre": "Normas de emisión para transporte", "nivel": "regional",
     "fuente": "transporte", "comunas": "todas",
     "credibilidad": {"p10": 0.6, "media": 0.75, "p90": 0.9}},
    {"id": "seia-planta", "nombre": "Proyecto industrial aprobado (ejemplo)", "nivel": "proyecto",
     "fuente": "industria", "comunas": [], "credibilidad": {"p10": 0.7, "media": 0.85, "p90": 0.95}},
]


def _base_real() -> list[dict]:
    """Una fila por comuna con estación: PM2,5 de invierno del año base."""
    with F_ESTACIONES.open(encoding="utf-8-sig", newline="") as fh:
        est = {f["estacion_id"]: f for f in csv.DictReader(fh)}
    comunas: dict[str, dict] = {}
    with F_ANUAL.open(encoding="utf-8-sig", newline="") as fh:
        for fila in csv.DictReader(fh):
            if fila["anio"] != str(ANIO_BASE) or not fila["pm25_media_invierno"]:
                continue
            meta = est[fila["estacion_id"]]
            comunas[meta["comuna"]] = {
                "codigo": meta["comuna"].lower().replace(" ", "-"),
                "nombre": meta["comuna"],
                "lat": float(meta["lat"]),
                "lon": float(meta["lon"]),
                "base": float(fila["pm25_media_invierno"]),
            }
    return sorted(comunas.values(), key=lambda c: c["nombre"])


def main() -> None:
    rng = np.random.default_rng(SEMILLA)
    comunas = _base_real()
    if not comunas:
        raise SystemExit("No hay línea base: corre antes datos/aire/fetch_sinca.py")
    politicas = [dict(p) for p in POLITICAS]
    politicas[2]["comunas"] = [comunas[0]["codigo"]]

    # Efecto anual inventado de cada política sobre cada comuna (µg/m³ por año).
    efecto = {
        "ppda-lena": {c["codigo"]: -0.45 - 0.01 * (c["base"] - 30) for c in comunas},
        "ppda-transporte": {c["codigo"]: -0.25 for c in comunas},
        "seia-planta": {c["codigo"]: (0.6 if i == 0 else 0.15 if i in (1, 2) else 0.0)
                        for i, c in enumerate(comunas)},
    }
    escenarios = [{"id": "base", "nombre": "Todos los planes vigentes",
                   "politicas_activas": [p["id"] for p in politicas]}]
    for p in politicas:
        escenarios.append({
            "id": f"sin-{p['id']}", "nombre": f"Sin: {p['nombre']}",
            "politicas_activas": [q["id"] for q in politicas if q["id"] != p["id"]],
        })

    trayectorias: dict = {}
    aportes: dict = {}
    for esc in escenarios:
        trayectorias[esc["id"]] = {}
        aportes[esc["id"]] = {}
        for c in comunas:
            pendiente = sum(
                efecto[pid][c["codigo"]] * next(p for p in politicas if p["id"] == pid)
                ["credibilidad"]["media"] for pid in esc["politicas_activas"])
            ruido = rng.normal(0, 0.15, len(ANIOS)).cumsum()
            p50 = [round(max(c["base"] + pendiente * (i + 1) + ruido[i], 5.0), 2)
                   for i in range(len(ANIOS))]
            ancho = [1.5 + 0.7 * i for i in range(len(ANIOS))]
            trayectorias[esc["id"]][c["codigo"]] = {"pm25_invierno": {
                "p10": [round(max(v - a, 3.0), 2) for v, a in zip(p50, ancho)],
                "p50": p50,
                "p90": [round(v + a, 2) for v, a in zip(p50, ancho)],
            }}
            aportes[esc["id"]][c["codigo"]] = {"pm25_invierno": [
                {"politica_id": pid,
                 "delta_p50_final": round(efecto[pid][c["codigo"]] * len(ANIOS) * next(
                     p for p in politicas if p["id"] == pid)["credibilidad"]["media"], 2)}
                for pid in esc["politicas_activas"]]}

    flujos = {esc["id"]: [
        {"anio": anio, "origen": comunas[i]["codigo"], "destino": comunas[j]["codigo"],
         "hogares": int(rng.integers(40, 900))}
        for anio in ANIOS for i, j in ((0, 3), (1, 4), (2, 5), (4, 0))
        if max(i, j) < len(comunas)] for esc in escenarios}

    salida = {
        "meta": {
            "version": "0.1", "es_ejemplo": True, "semilla": SEMILLA,
            "aviso": "Datos de ejemplo para la interfaz. Solo la línea base es real.",
            "anio_base": ANIO_BASE, "anios": ANIOS,
        },
        "variables": [{"id": "pm25_invierno", "nombre": "PM2,5 de invierno (mayo a agosto)",
                       "unidad": "µg/m³", "mejor": "menor"}],
        "comunas": [{"codigo": c["codigo"], "nombre": c["nombre"], "lat": c["lat"],
                     "lon": c["lon"], "base": {"pm25_invierno": c["base"]}} for c in comunas],
        "tipos_hogar": [
            {"id": "sensible-aire", "nombre": "Sensible a la contaminación",
             "pesos": {"pm25_invierno": 0.8, "seguridad": 0.2}},
            {"id": "prioriza-seguridad", "nombre": "Prioriza seguridad",
             "pesos": {"pm25_invierno": 0.2, "seguridad": 0.8}},
            {"id": "equilibrado", "nombre": "Equilibrado",
             "pesos": {"pm25_invierno": 0.5, "seguridad": 0.5}},
        ],
        "politicas": politicas,
        "escenarios": escenarios,
        "trayectorias": trayectorias,
        "aportes": aportes,
        "flujos": flujos,
    }
    F_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    F_SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{F_SALIDA.relative_to(RAIZ)}: {len(comunas)} comunas, {len(escenarios)} escenarios, "
          f"{len(ANIOS)} años")


if __name__ == "__main__":
    main()
