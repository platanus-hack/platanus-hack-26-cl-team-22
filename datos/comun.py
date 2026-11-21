"""Shared helpers for the data download scripts: commune keys and cached downloads.

Every source except the Coordinador names communes instead of using the CUT code, with varying
accents, case and spacing ("Til til", "Tiltil", "TILTIL"). `cut_de` maps any of those to the
five-digit CUT of data/comunas_rm.csv. `descargar` caches each raw response under data/raw/
(ignored by git) and records URL, download date and SHA-256 in the source's manifest.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMUNAS = ROOT / "data" / "comunas_rm.csv"
USER_AGENT = "team22-simulation/1.0 (+https://github.com/platanus-hack)"


def clave(nombre: str) -> str:
    """Name key: no accents, lower case, letters only ("Til til" -> "tiltil")."""
    plano = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", plano.lower())


def comunas_rm() -> list[dict[str, str]]:
    """Rows of data/comunas_rm.csv: codigo_comuna, comuna, provincia, ..."""
    with COMUNAS.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def cut_de(nombre: str) -> str | None:
    """CUT of an RM commune name, or None when the name is not an RM commune."""
    return {clave(r["comuna"]): r["codigo_comuna"] for r in comunas_rm()}.get(clave(nombre))


def descargar(url: str, ruta: Path, manifiesto: dict, *, datos: dict | None = None,
              pausa: float = 1.0) -> bytes:
    """GET (or POST form `datos`) cached at `ruta`; records it in `manifiesto`."""
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        cuerpo = urllib.parse.urlencode(datos).encode() if datos is not None else None
        req = urllib.request.Request(url, data=cuerpo, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=300) as resp:
            ruta.write_bytes(resp.read())
        time.sleep(pausa)  # be gentle with public services
    contenido = ruta.read_bytes()
    entrada = {"url": url, "descargado": dt.date.fromtimestamp(ruta.stat().st_mtime).isoformat(),
               "sha256": hashlib.sha256(contenido).hexdigest()}
    if datos is not None:
        entrada["post"] = datos
    manifiesto[str(ruta.relative_to(ROOT))] = entrada
    return contenido


def escribir_manifiesto(carpeta: Path, fuente: str, manifiesto: dict, **extra) -> None:
    (carpeta / "manifest.json").write_text(json.dumps(
        {"fuente": fuente, **extra, "archivos": manifiesto}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
