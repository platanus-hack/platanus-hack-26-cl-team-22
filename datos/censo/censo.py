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


# --- External flows ----------------------------------------------------------------------
# People who enter or leave the RM, which the internal move matrices leave out.

EXTERNOS = ["llegan_otras_regiones", "salen_a_otras_regiones", "llegan_extranjero",
            "menores_5", "residencia_ignorada"]
P11_AUN_NO_NACIA = 1
P11_OTRO_PAIS = range(4, 10)  # 4 Perú, 5 Argentina, 6 Bolivia, 7 Ecuador, 8 Colombia, 9 Otro


def region_conocida(codigo: pd.Series) -> pd.Series:
    """Region of a comuna code or of a 'region known, comuna unknown' code (RR000); else 0."""
    valido = (codigo >= 1000) & (codigo <= 16999)
    return (codigo // 1000).where(valido, 0)


def _por_comuna(conteos: dict[str, pd.Series]) -> pd.DataFrame:
    tabla = pd.DataFrame({c: conteos[c] for c in EXTERNOS}).fillna(0).astype(int)
    tabla.index.name = "codigo"
    return tabla.reset_index()[["codigo", *EXTERNOS]]


def externos_2017(personas: pd.DataFrame) -> pd.DataFrame:
    """Count Censo 2017 people entering or leaving each RM comuna over 2012-2017.

    Uses the same rebuild as `pares_2017`: destination is the usual residence; "this comuna"
    five years ago is only usable when the person was counted at home.
    """
    p10, p11 = personas["P10"], personas["P11"]
    en_casa = p10.isin(P10_EN_ESTA_COMUNA)
    destino = personas["COMUNA"].where(en_casa)
    destino = destino.mask(p10 == P10_OTRA_COMUNA, personas["P10COMUNA"]).fillna(0).astype(int)
    origen = personas["COMUNA"].where((p11 == P11_ESTA_COMUNA) & en_casa)
    origen = origen.mask(p11 == P11_OTRA_COMUNA, personas["P11COMUNA"]).fillna(0).astype(int)

    vive_rm = es_comuna_rm(destino)
    region_origen = region_conocida(origen)
    region_destino = region_conocida(destino)
    origen_comuna_o_region = (p11 == P11_OTRA_COMUNA) | ((p11 == P11_ESTA_COMUNA) & en_casa)

    llega_region = vive_rm & origen_comuna_o_region & (region_origen > 0) & (region_origen != 13)
    llega_pais = vive_rm & p11.isin(P11_OTRO_PAIS)
    no_nacia = vive_rm & (p11 == P11_AUN_NO_NACIA)
    interno = vive_rm & origen_comuna_o_region & es_comuna_rm(origen)
    ignorada = vive_rm & ~(llega_region | llega_pais | no_nacia | interno)
    sale = es_comuna_rm(origen) & (region_destino > 0) & (region_destino != 13)

    return _por_comuna({
        "llegan_otras_regiones": destino[llega_region].value_counts(),
        "salen_a_otras_regiones": origen[sale].value_counts(),
        "llegan_extranjero": destino[llega_pais].value_counts(),
        "menores_5": destino[no_nacia].value_counts(),
        "residencia_ignorada": destino[ignorada].value_counts(),
    })


def externos_2024(filas: list[tuple]) -> pd.DataFrame:
    """External flows per RM comuna from INE table D5 sheet "2" (2019-2024).

    "Comuna ignorada" of another region counts as arriving from another region; of the RM,
    as unknown origin (the comuna is what the model needs).
    """
    encabezado = next((f for f in filas if f and f[0] == "Código región"), None)
    if encabezado is None:
        raise ValueError("D5 header row 'Código región' not found: the sheet layout changed")
    comunas = [f for f in filas
               if f and len(f) > D5_COL_CODIGO and isinstance(f[D5_COL_CODIGO], int)
               and f[D5_COL_CODIGO] > 0]
    codigos = [f[D5_COL_CODIGO] for f in comunas]
    col = {_norm(nombre): j for j, nombre in enumerate(encabezado)}
    fin_comunas = D5_COLUMNAS_FIJAS + len(comunas)
    ign_region = [j for j in range(fin_comunas, len(encabezado))
                  if _norm(encabezado[j]).startswith("comuna ignorada")]
    ign_rm = [j for j in ign_region if "metropolitana" in _norm(encabezado[j])]

    def n(valor) -> int:
        return int(valor) if isinstance(valor, (int, float)) else 0

    registros = []
    for k, fila in enumerate(comunas):
        codigo = fila[D5_COL_CODIGO]
        if codigo // 1000 != 13:
            continue
        otras = sum(n(fila[D5_COLUMNAS_FIJAS + m]) for m, c in enumerate(codigos)
                    if c // 1000 != 13)
        otras += sum(n(fila[j]) for j in ign_region if j not in ign_rm)
        salen = sum(n(otra[D5_COLUMNAS_FIJAS + k]) for otra in comunas
                    if otra[D5_COL_CODIGO] // 1000 != 13)
        ignorada = sum(n(fila[j]) for j in ign_rm) + sum(
            n(fila[col[_norm(nombre)]]) for nombre in (
                "Residencia habitual hace cinco años con región ignorada",
                "Residencia habitual hace cinco años ignorada"))
        registros.append({
            "codigo": codigo,
            "llegan_otras_regiones": otras,
            "salen_a_otras_regiones": salen,
            "llegan_extranjero": n(fila[col[_norm(
                "Residencia habitual hace cinco años fuera del país")]]),
            "menores_5": n(fila[col[_norm("Aún no nacían (menores de 5 años)")]]),
            "residencia_ignorada": ignorada,
        })
    return pd.DataFrame(registros, columns=["codigo", *EXTERNOS])


def sumar_proyeccion(filas: list[tuple], anios: list[int]) -> dict[tuple[int, int], int]:
    """Total projected population per (RM comuna, year) from INE's comuna projection sheet.

    The sheet has one row per comuna, sex and single age, and one 'Poblacion YYYY' column per
    year. Values are fractional estimates; totals are rounded after summing.
    """
    encabezado = filas[0]
    col = {a: encabezado.index(f"Poblacion {a}") for a in anios}
    i_comuna = encabezado.index("Comuna")
    suma: dict[tuple[int, int], float] = {}
    for fila in filas[1:]:
        codigo = fila[i_comuna]
        if not isinstance(codigo, int) or not es_comuna_rm(pd.Series([codigo])).iloc[0]:
            continue
        for a, j in col.items():
            suma[(codigo, a)] = suma.get((codigo, a), 0.0) + float(fila[j])
    return {k: round(v) for k, v in suma.items()}


# --- Foreign-born stock ------------------------------------------------------------------
# P12: place of birth; 3-8 = another country (Perú, Argentina, Bolivia, Ecuador, Colombia,
# Otro). P12A_LLEGADA: year of arrival in Chile (9998 not applicable, 9999 missing).
P12_OTRO_PAIS = range(3, 9)
ANIO_CORTE_REDES = 2012


def stock_extranjero_2017(personas: pd.DataFrame) -> dict[int, tuple[int, int]]:
    """{RM comuna of usual residence: (born abroad, born abroad and arrived before 2012)}."""
    p10 = personas["P10"]
    destino = personas["COMUNA"].where(p10.isin(P10_EN_ESTA_COMUNA))
    destino = destino.mask(p10 == P10_OTRA_COMUNA, personas["P10COMUNA"]).fillna(0).astype(int)
    extranjero = personas["P12"].isin(P12_OTRO_PAIS) & es_comuna_rm(destino)
    llegada = personas["P12A_LLEGADA"]
    antes = extranjero & (llegada < ANIO_CORTE_REDES) & (llegada > 1900)
    total = destino[extranjero].value_counts()
    previo = destino[antes].value_counts()
    return {int(c): (int(total[c]), int(previo.get(c, 0))) for c in total.index}
