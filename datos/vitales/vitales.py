"""Read births and deaths per RM comuna from INE vital statistics yearbooks (sheet 122-04).

The sheet lists every region, then its provinces and comunas by name, without codes. Columns
changed over the years: until 2020 there is one column per concept; from 2021 births and deaths
are split by sex (Hombre, Mujer, Indeterminado) and are summed here.
"""

from __future__ import annotations

import unicodedata

SEXOS = {"hombre", "mujer", "indeterminado"}


def _norm(texto) -> str:
    plano = unicodedata.normalize("NFKD", str(texto or ""))
    plano = "".join(ch for ch in plano if not unicodedata.combining(ch))
    return " ".join(plano.lower().split())


def _clave(nombre) -> str:
    """Name key that ignores accents, case, spaces and apostrophes ('Til Til' = 'Tiltil')."""
    return "".join(ch for ch in _norm(nombre) if ch.isalnum())


def _columnas(filas: list[tuple], bloque: range, es_concepto) -> list[int]:
    """Columns of one concept: its header cell plus the sex columns right under it.

    The header may sit on any row of the header block (deaths are one row below births in
    2015, 2019 and 2020).
    """
    for r in bloque:
        enc = filas[r]
        inicio = next((j for j, c in enumerate(enc) if es_concepto(_norm(c))), None)
        if inicio is None:
            continue
        sub = filas[r + 1]
        cols = [inicio]
        if inicio < len(sub) and _norm(sub[inicio]) in SEXOS:
            for j in range(inicio + 1, len(enc)):
                if enc[j] not in (None, "") or j >= len(sub) or _norm(sub[j]) not in SEXOS:
                    break
                cols.append(j)
        return cols
    raise ValueError("Header not found in sheet 122-04: the layout changed")


def _valor(fila: tuple, cols: list[int]) -> int:
    return sum(int(fila[j]) for j in cols if j < len(fila) and isinstance(fila[j], (int, float)))


def leer_anuario(filas: list[tuple], codigos: dict[str, int]) -> dict[int, tuple[int, int]]:
    """Return {comuna code: (births, deaths)} for the RM comunas in `codigos` (name -> code).

    Province rows that share a comuna's name (Santiago, Talagante, Melipilla) come first, so
    the last row with that name is the comuna. The 52 comunas must add up to the RM row.
    """
    i_enc = next((i for i, f in enumerate(filas)
                  if any(_norm(c) == "nacidos vivos" for c in f)), None)
    if i_enc is None:
        raise ValueError("'Nacidos Vivos' header not found in sheet 122-04: the layout changed")
    bloque = range(max(i_enc - 1, 0), i_enc + 2)
    c_nac = _columnas(filas, bloque, lambda t: t == "nacidos vivos")
    c_def = _columnas(filas, bloque,
                      lambda t: t == "generales" or t.startswith("defunciones generales"))

    i_rm = next((i for i, f in enumerate(filas)
                 if f and _norm(f[0]).endswith("metropolitana")), None)
    if i_rm is None:
        raise ValueError("RM block not found in sheet 122-04")
    por_clave = {_clave(n): c for n, c in codigos.items()}
    leidos: dict[int, tuple[int, int]] = {}
    for fila in filas[i_rm + 1:]:
        nombre = str(fila[0] or "").strip()
        if nombre and nombre.upper() == nombre and any(ch.isalpha() for ch in nombre):
            break  # next region (regions are written in capitals)
        codigo = por_clave.get(_clave(nombre))
        if codigo is not None:
            leidos[codigo] = (_valor(fila, c_nac), _valor(fila, c_def))

    faltan = [n for n, c in codigos.items() if c not in leidos]
    if faltan:
        raise ValueError(f"Comunas not found in the RM block: {', '.join(faltan)}")
    total = (_valor(filas[i_rm], c_nac), _valor(filas[i_rm], c_def))
    suma = tuple(sum(v[k] for v in leidos.values()) for k in (0, 1))
    if suma != total:
        raise ValueError(f"Comunas add up to {suma} but the RM total row says {total}")
    return leidos
