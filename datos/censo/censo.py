"""Pure rules that turn INE census data into RM inter-comuna move matrices.

A matrix has one row per (origin, destination) pair of RM comunas: where a person lived
five years before the census and where they usually live at the census. The diagonal holds
people who lived in the same comuna both times. Codes are the 5-digit CUT (13101 = Santiago).
"""

from __future__ import annotations

import unicodedata

import pandas as pd

COLUMNAS = ["codigo_origen", "codigo_destino", "personas"]

# Censo 2017 person questionnaire (manual de usuario Censo 2017, 16 regiones).
# P10: usual residence. 1 this dwelling, 2 another dwelling (same comuna), 3 another comuna.
# P11: residence five years ago. 2 this comuna (where counted), 3 another comuna.
P10_EN_ESTA_COMUNA = (1, 2)
P10_OTRA_COMUNA = 3
P11_ESTA_COMUNA = 2
P11_OTRA_COMUNA = 3

# INE table D5, sheet "2": the origin comuna columns start after these.
D5_COLUMNAS_FIJAS = 9
D5_COL_CODIGO = 4
D5_COL_NOMBRE = 5
D5_COL_NO_MIGRANTE = 7


def es_comuna_rm(codigo: pd.Series) -> pd.Series:
    """True for a real RM comuna code (13xxx), False for 13000, 997, 98, 99 or others."""
    return (codigo // 1000 == 13) & (codigo % 1000 != 0)


def pares_2017(personas: pd.DataFrame) -> pd.DataFrame:
    """Aggregate Censo 2017 person rows into RM origin-destination counts.

    2017 was a de facto census: COMUNA is where the person was counted. The destination
    is rebuilt from the usual residence (P10/P10COMUNA). "This comuna" in P11 refers to
    the comuna where the person was counted, so it is only usable when that is also the
    usual residence; otherwise the row is dropped.
    """
    p10, p11 = personas["P10"], personas["P11"]
    vive_donde_fue_censado = p10.isin(P10_EN_ESTA_COMUNA)

    destino = personas["COMUNA"].where(vive_donde_fue_censado)
    destino = destino.mask(p10 == P10_OTRA_COMUNA, personas["P10COMUNA"])

    origen = personas["COMUNA"].where((p11 == P11_ESTA_COMUNA) & vive_donde_fue_censado)
    origen = origen.mask(p11 == P11_OTRA_COMUNA, personas["P11COMUNA"])

    validos = (destino.notna() & origen.notna()
               & es_comuna_rm(destino.fillna(0).astype(int))
               & es_comuna_rm(origen.fillna(0).astype(int)))
    pares = pd.DataFrame({
        "codigo_origen": origen[validos].astype(int),
        "codigo_destino": destino[validos].astype(int),
    })
    return (pares.groupby(["codigo_origen", "codigo_destino"]).size()
            .rename("personas").reset_index()[COLUMNAS])


def _norm(texto) -> str:
    plano = unicodedata.normalize("NFKD", str(texto or ""))
    plano = "".join(ch for ch in plano if not unicodedata.combining(ch))
    return " ".join(plano.lower().split())


def matriz_2024(filas: list[tuple]) -> pd.DataFrame:
    """Reshape INE table D5 sheet "2" (rows = current comuna, columns = comuna 5 years ago).

    Origin columns follow the same order as the comuna rows; the function checks it by
    name and raises ValueError if they drift. The diagonal ("-") is taken from the
    "No migrante interno comunal" column.
    """
    encabezado = next((f for f in filas if f and f[0] == "Código región"), None)
    if encabezado is None:
        raise ValueError("D5 header row 'Código región' not found: the sheet layout changed")
    comunas = [f for f in filas
               if f and len(f) > D5_COL_CODIGO and isinstance(f[D5_COL_CODIGO], int)
               and f[D5_COL_CODIGO] > 0]
    if len(encabezado) < D5_COLUMNAS_FIJAS + len(comunas):
        raise ValueError(f"D5 has {len(comunas)} comuna rows but only "
                         f"{len(encabezado) - D5_COLUMNAS_FIJAS} origin columns: "
                         "the sheet layout changed")

    columna_de = {}
    for k, fila in enumerate(comunas):
        j = D5_COLUMNAS_FIJAS + k
        if _norm(encabezado[j]) != _norm(fila[D5_COL_NOMBRE]):
            raise ValueError(f"D5 column {j} is {encabezado[j]!r}, expected "
                             f"{fila[D5_COL_NOMBRE]!r}: the sheet layout changed")
        columna_de[fila[D5_COL_CODIGO]] = j

    rm = [f for f in comunas if es_comuna_rm(pd.Series([f[D5_COL_CODIGO]])).iloc[0]]
    registros = []
    for fila in rm:
        destino = fila[D5_COL_CODIGO]
        for otra in rm:
            origen = otra[D5_COL_CODIGO]
            valor = (fila[D5_COL_NO_MIGRANTE] if origen == destino
                     else fila[columna_de[origen]])
            registros.append((origen, destino, int(valor)))
    return pd.DataFrame(registros, columns=COLUMNAS)


def completar_rm(pares: pd.DataFrame, codigos: list[int]) -> pd.DataFrame:
    """Return every (origin, destination) pair of `codigos`, with 0 where nobody moved."""
    todos = pd.MultiIndex.from_product([sorted(codigos)] * 2,
                                       names=["codigo_origen", "codigo_destino"])
    serie = pares.set_index(["codigo_origen", "codigo_destino"])["personas"]
    return (serie.reindex(todos, fill_value=0).astype(int)
            .rename("personas").reset_index()[COLUMNAS])
