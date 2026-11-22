"""Split viz/datos/licitaciones.json into one small file per commune for the interface.

The full file weighs several MB and lives outside viz/public, so the browser cannot fetch it. The interface
only needs the selected commune, so each commune gets its own file under viz/public/datos/licitaciones/.
Every file repeats the few meta fields the view shows, so one request is enough.

Run: python -I datos/viz/partir_licitaciones.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ORIGEN = RAIZ / "viz" / "datos" / "licitaciones.json"
DESTINO = RAIZ / "viz" / "public" / "datos" / "licitaciones"
CAMPOS = (
    "codigo_externo",
    "nombre",
    "estado",
    "sector",
    "monto_estimado_clp",
    "monto_adjudicado_clp",
    "numero_oferentes",
    "aporte_credibilidad",
)
LARGO_NOMBRE = 140


def partir(origen: Path = ORIGEN, destino: Path = DESTINO) -> int:
    """Write one file per commune and return how many were written."""
    datos = json.loads(origen.read_text(encoding="utf-8"))
    meta = datos["meta"]
    destino.mkdir(parents=True, exist_ok=True)
    escritos = 0
    for codigo, comuna in datos["comunas"].items():
        if not re.fullmatch(r"\d{5}", codigo):
            continue
        licitaciones = []
        for lic in comuna["licitaciones"]:
            fila = {k: lic.get(k) for k in CAMPOS}
            fila["nombre"] = str(fila["nombre"] or "")[:LARGO_NOMBRE]
            licitaciones.append(fila)
        salida = {
            "codigo": codigo,
            "anio": meta["anio"],
            "fuente": "ChileCompra Datos Abiertos",
            "max_n_efectivo": meta["max_n_efectivo"],
            **{k: v for k, v in comuna.items() if k != "licitaciones"},
            "licitaciones": licitaciones,
        }
        texto = json.dumps(salida, ensure_ascii=False, separators=(",", ":"))
        (destino / f"{codigo}.json").write_text(texto, encoding="utf-8", newline="\n")
        escritos += 1
    return escritos


if __name__ == "__main__":
    print(f"{partir()} comunas en {DESTINO.relative_to(RAIZ)}")
