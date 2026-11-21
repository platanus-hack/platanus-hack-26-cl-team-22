"""Read housing building permits per RM comuna from MINVU's yearly table.

Source table: "Viviendas unidades y superficie según año y comuna" (Centro de Estudios de
Ciudad y Territorio, MINVU), built from INE's Formulario Único de Estadística de Edificación.
One sheet per measure; rows are region totals followed by their comunas (by name, no code);
columns are years, some with footnote marks such as "2018 (***)".
"""

from __future__ import annotations

from datos.vitales.vitales import clave_nombre

HOJAS = {"viviendas": "número_total", "departamentos": "número_departamentos",
         "casas": "número_casas", "m2": "m2_total"}
REGION_RM = "metropolitana"


def _anio(celda) -> int | None:
    texto = str(celda or "").strip().split(" ")[0]
    return int(texto) if texto.isdigit() and len(texto) == 4 else None


def _num(celda) -> int:
    return round(float(celda)) if isinstance(celda, (int, float)) else 0


def _leer_hoja(filas: list[tuple], codigos: dict[str, int], anios: list[int],
               nombre_hoja: str) -> dict[tuple[int, int], int]:
    encabezado = next((f for f in filas if f and f[0] == "Región"), None)
    if encabezado is None:
        raise ValueError(f"Header row 'Región' not found in sheet {nombre_hoja}")
    col = {_anio(c): j for j, c in enumerate(encabezado) if _anio(c) is not None}
    faltan_anios = [a for a in anios if a not in col]
    if faltan_anios:
        raise ValueError(f"Years {faltan_anios} not found in sheet {nombre_hoja}")

    rm = [f for f in filas if f and clave_nombre(f[0]) == REGION_RM]
    total = next((f for f in rm if not f[1]), None)
    por_clave = {clave_nombre(n): c for n, c in codigos.items()}
    leidos = {por_clave[clave_nombre(f[1])]: f for f in rm
              if f[1] and clave_nombre(f[1]) in por_clave}
    faltan = [n for n, c in codigos.items() if c not in leidos]
    if faltan:
        raise ValueError(f"Comunas not found in sheet {nombre_hoja}: {', '.join(faltan)}")

    out = {}
    for anio in anios:
        j = col[anio]
        for codigo, fila in leidos.items():
            out[(codigo, anio)] = _num(fila[j])
        if total is not None and len(codigos) == len(leidos):
            suma = sum(out[(c, anio)] for c in leidos)
            if isinstance(total[j], (int, float)) and suma != _num(total[j]):
                raise ValueError(f"Sheet {nombre_hoja}, {anio}: comunas add up to {suma} "
                                 f"but the RM row says {_num(total[j])}")
    return out


def leer_permisos(hojas: dict[str, list[tuple]], codigos: dict[str, int],
                  anios: list[int]) -> dict[tuple[int, int], dict[str, int]]:
    """Return {(comuna code, year): {viviendas, departamentos, casas, m2}}.

    `hojas` maps sheet name -> rows (with cached values, not formulas). The comunas must add
    up to the RM row of each sheet, when that row holds a number.
    """
    medidas = {m: _leer_hoja(hojas[h], codigos, anios, h) for m, h in HOJAS.items()}
    return {k: {m: medidas[m][k] for m in HOJAS} for k in medidas["viviendas"]}
