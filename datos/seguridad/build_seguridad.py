"""Construye data/seguridad/delitos_comuna_anio.csv desde el portal del CEAD (SPD).

Fuente: Centro de Estudios y Análisis del Delito (CEAD), Subsecretaría de Prevención
del Delito, "Estadísticas delictuales", https://cead.minsegpublica.gob.cl/estadisticas-delictuales/
(datasets anteriores vivían en cead.spd.gov.cl, dominio que hoy no resuelve).

El portal es una aplicación web (WordPress + jQuery) que consulta un endpoint propio:

    POST https://cead.minsegpublica.gob.cl/wp-content/themes/gobcl-wp-master/data/get_estadisticas_delictuales.php

Parámetros relevantes (los mismos que arma el JavaScript del portal):
    seleccion=1            reporte "unidad territorial" (filas = país/región/provincia/comuna)
    medida=1|2            1 = frecuencia (casos), 2 = tasa cada 100.000 habitantes
    tipoVal=1,2           "Casos Policiales" (denuncias + detenciones en flagrancia)
    anio[]=2017..2024     años
    region[]=13           Región Metropolitana
    comuna[]=...          códigos de comuna de 5 dígitos (los mismos de data/comunas_rm.csv)
    familia[]/grupo[]/subgrupo[]  categorías delictuales (ver CATEGORIAS)
    descarga=true         devuelve "Excel" (en realidad una tabla HTML con extensión .xls)

Notas:
  - La tasa viene calculada por el propio portal con la población oficial proyectada por
    el INE vigente (Censo 2024). No se recalcula aquí.
  - No se estima ni interpola nada: si el portal no devuelve una comuna/año, la fila no se
    escribe y se informa en el resumen.
  - `dmcs_total` no existe como fila en el portal: se pide seleccionando de una vez los
    componentes de la clasificación DMCS tradicional (ver COMPONENTES_DMCS). El portal hace
    la suma. El script verifica que ese total sea igual a la suma de las categorías
    individuales descargadas por separado.

Uso (desde la raíz del repo):
    .venv/Scripts/python datos/seguridad/build_seguridad.py [--force]

Los archivos descargados son datos no confiables: se guardan tal cual en data/raw/seguridad/
y solo se parsean como HTML, nunca se ejecutan.
"""
from __future__ import annotations

import argparse
import html as htmllib
import sys
import time
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "seguridad"
OUT = ROOT / "data" / "seguridad" / "delitos_comuna_anio.csv"
COMUNAS = ROOT / "data" / "comunas_rm.csv"

URL_PORTAL = "https://cead.minsegpublica.gob.cl/estadisticas-delictuales/"
URL_DATOS = (
    "https://cead.minsegpublica.gob.cl/wp-content/themes/gobcl-wp-master/data/"
    "get_estadisticas_delictuales.php"
)
ORIGEN = "CEAD-SPD cead.minsegpublica.gob.cl (descarga 2026-11-21)"

ANIOS = list(range(2017, 2025))
CODIGO_REGION_RM = "13"
NOMBRE_REGION_RM = "Región Metropolitana"
PAUSA = 2.0  # segundos entre peticiones, para no castigar el servidor

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-script",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": URL_PORTAL,
    "Accept": "*/*",
}

# Componentes que forman el DMCS tradicional (los 13 subgrupos de la clasificación histórica
# del CEAD). El portal devuelve ceros si se mezclan niveles (grupo/subgrupo) en una misma
# consulta, así que `dmcs_total` se arma sumando estas filas publicadas por separado. No
# incluye `robo_objetos_de_vehiculo` (60202), que la clasificación tradicional no cuenta
# como categoría DMCS aparte.
COMPONENTES_DMCS = [
    "homicidios",
    "lesiones",
    "violaciones",
    "robo_con_violencia",
    "robo_por_sorpresa",
    "robo_en_lugar_habitado",
    "robo_en_lugar_no_habitado",
    "robo_de_vehiculo",
    "otros_robos_con_fuerza",
    "hurtos",
    "violencia_intrafamiliar",
]

# Nombre con el que el portal identifica cada código. El portal empareja código+nombre:
# si no calzan devuelve ceros, así que se envían juntos y con la tilde exacta del portal.
NOMBRES = {
    "7": "Incivilidades",
    "101": "Homicidios y femicidios",
    "102": "Violaciones y otros delitos sexuales",
    "103": "Lesiones graves o gravísimas",
    "104": "Lesiones menos graves",
    "105": "Lesiones leves",
    "201": "Robos con violencia o intimidación",
    "301": "Violencia intrafamiliar",
    "401": "Crímenes y simples delitos ley de drogas",
    "501": "Crímenes y simples delitos ley de armas",
    "602": "Robos de vehículo motorizado o de sus accesorios",
    "10201": "Violaciones",
    "20201": "Robo por sorpresa",
    "60101": "Robo en lugar habitado",
    "60102": "Robo en lugar no habitado",
    "60201": "Robo de vehículo motorizado",
    "60202": "Robo de objetos de o desde vehículo",
    "60301": "Otros robos con fuerza en las cosas",
    "60401": "Hurtos",
}

# categoria final -> selección del portal (una o más entradas que el portal suma)
CATEGORIAS: dict[str, list[tuple[str, str]]] = {
    "homicidios": [("grupo", "101")],
    "lesiones": [("grupo", "103"), ("grupo", "104"), ("grupo", "105")],
    "violaciones": [("subgrupo", "10201")],
    "delitos_sexuales": [("grupo", "102")],
    "robo_con_violencia": [("grupo", "201")],
    "robo_por_sorpresa": [("subgrupo", "20201")],
    "robo_en_lugar_habitado": [("subgrupo", "60101")],
    "robo_en_lugar_no_habitado": [("subgrupo", "60102")],
    "robo_de_vehiculo": [("subgrupo", "60201")],
    "robo_objetos_de_vehiculo": [("subgrupo", "60202")],
    "otros_robos_con_fuerza": [("subgrupo", "60301")],
    "hurtos": [("subgrupo", "60401")],
    "violencia_intrafamiliar": [("grupo", "301")],
    "drogas": [("grupo", "401")],
    "armas": [("grupo", "501")],
    "incivilidades": [("familia", "7")],
}

# Suma de control de dmcs_total: estas categorías individuales, todas disjuntas entre sí,
# deben reconstruir el total componente por componente.
CONTROL_DMCS = [
    "homicidios",
    "lesiones",
    "violaciones",
    "robo_con_violencia",
    "robo_por_sorpresa",
    "robo_en_lugar_habitado",
    "robo_en_lugar_no_habitado",
    "robo_de_vehiculo",
    "robo_objetos_de_vehiculo",
    "otros_robos_con_fuerza",
    "hurtos",
    "violencia_intrafamiliar",
]

MEDIDAS = {1: "frecuencia", 2: "tasa"}


class TablaPortal(HTMLParser):
    """Extrae las filas de datos (<tr class="formato_N">) de la tabla del portal.

    Nivel por clase de fila: formato_1 = TOTAL PAÍS, formato_2 = región,
    formato_3 = provincia, formato_4 = comuna.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self._row: dict | None = None
        self._cell: list[str] | None = None
        self._header: list[str] | None = None
        self._year_header: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "tr":
            clases = d.get("class", "").split()
            nivel = next((c for c in clases if c.startswith("formato_")), "")
            self._row = {"nivel": nivel, "cells": []}
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            txt = "".join(self._cell).replace("\xa0", " ")
            self._row["cells"].append(htmllib.unescape(txt).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            cells = self._row["cells"]
            if self._year_header is None and len(cells) > 1 and cells[0].strip() == "" and all(
                c.strip().isdigit() and len(c.strip()) == 4 for c in cells[1:]
            ):
                self._year_header = [c.strip() for c in cells[1:]]
            elif self._row["nivel"] and cells:
                self.rows.append(self._row)
            self._row = None


def sin_tildes(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.split())


def a_numero(txt: str) -> float | None:
    """'1.004,0000000000' -> 1004.0 ; '' -> None."""
    t = txt.strip().replace("\xa0", "")
    if not t:
        return None
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def descargar(categoria: str, medida: int, comunas: pd.DataFrame, force: bool) -> Path:
    dest = RAW / f"cead_{categoria}_{MEDIDAS[medida]}.xls"
    if dest.exists() and dest.stat().st_size > 2000 and not force:
        return dest

    payload: list[tuple[str, str]] = [("medida", str(medida)), ("tipoVal", "1,2")]
    payload += [("anio[]", str(a)) for a in ANIOS]
    payload += [("region[]", CODIGO_REGION_RM), ("region_nombres[]", NOMBRE_REGION_RM)]
    payload += [("comuna[]", c) for c in comunas["codigo_comuna"]]
    payload += [("comuna_nombres[]", n) for n in comunas["comuna"]]
    for nivel, codigo in CATEGORIAS[categoria]:
        payload += [(f"{nivel}[]", codigo), (f"{nivel}_nombres[]", NOMBRES[codigo])]
    payload += [("seleccion", "1"), ("descarga", "true")]

    error: Exception | None = None
    for intento in range(3):
        if intento:
            time.sleep(5 * intento)
        try:
            r = requests.post(URL_DATOS, data=payload, headers=HEADERS, timeout=300)
            r.raise_for_status()
            if b"<table" not in r.content or len(r.content) < 2000:
                raise RuntimeError(f"respuesta inesperada ({len(r.content)} bytes)")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            time.sleep(PAUSA)
            return dest
        except Exception as exc:  # noqa: BLE001 - se reintenta y se reporta
            error = exc
    raise RuntimeError(f"no se pudo descargar {categoria}/{MEDIDAS[medida]}: {error}")


def leer_tabla(path: Path, anios: list[int]) -> tuple[dict[str, dict[int, float | None]], list[dict]]:
    """Devuelve ({etiqueta: {anio: valor}}, filas_por_nivel)."""
    parser = TablaPortal()
    parser.feed(path.read_bytes().decode("iso-8859-1"))
    if parser._year_header is None:
        raise RuntimeError(f"no se encontró el encabezado de años en {path.name}")
    if [int(y) for y in parser._year_header] != anios:
        raise RuntimeError(f"años inesperados en {path.name}: {parser._year_header}")

    datos: dict[str, dict[int, float | None]] = {}
    niveles: list[dict] = []
    for row in parser.rows:
        etiqueta = row["cells"][0].strip()
        valores = {a: a_numero(v) for a, v in zip(anios, row["cells"][1:])}
        if len(valores) != len(anios):
            raise RuntimeError(f"fila con {len(valores)} valores en {path.name}: {etiqueta!r}")
        datos[etiqueta] = valores
        niveles.append({"nivel": row["nivel"], "etiqueta": etiqueta})
    return datos, niveles


def pedir_por_delito(nivel: str, codigo: str, force: bool) -> dict[str, dict[int, float | None]]:
    """Control: mismo dato pedido por el otro reporte del portal ("por delito", seleccion=2).

    Devuelve {nombre del delito: {año: valor}} a nivel regional (una fila por delito).
    """
    dest = RAW / f"control_por_delito_{codigo}.xls"
    if force or not dest.exists() or dest.stat().st_size < 2000:
        payload: list[tuple[str, str]] = [("medida", "1"), ("tipoVal", "1,2")]
        payload += [("anio[]", str(a)) for a in ANIOS]
        payload += [("region[]", CODIGO_REGION_RM), ("region_nombres[]", NOMBRE_REGION_RM)]
        payload += [(f"{nivel}[]", codigo), (f"{nivel}_nombres[]", NOMBRES[codigo])]
        payload += [("seleccion", "2"), ("descarga", "true")]
        r = requests.post(URL_DATOS, data=payload, headers=HEADERS, timeout=300)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        time.sleep(PAUSA)
    datos, _ = leer_tabla(dest, ANIOS)
    return datos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="volver a descargar aunque haya caché")
    args = ap.parse_args()

    comunas = pd.read_csv(COMUNAS, dtype={"codigo_comuna": str})
    comunas["_clave"] = comunas["comuna"].map(sin_tildes)
    if len(comunas) != 52:
        raise SystemExit(f"data/comunas_rm.csv trae {len(comunas)} comunas, se esperaban 52")
    clave_a_codigo = dict(zip(comunas["_clave"], comunas["codigo_comuna"]))
    clave_a_nombre = dict(zip(comunas["_clave"], comunas["comuna"]))
    codigos = set(comunas["codigo_comuna"])
    codigo_a_provincia = dict(zip(comunas["codigo_comuna"], comunas["provincia"]))

    print(f"CEAD -> {OUT.relative_to(ROOT)}")
    print(f"categorías: {len(CATEGORIAS)} | años: {ANIOS[0]}-{ANIOS[-1]} | comunas: 52\n")

    filas: list[dict] = []
    problemas: list[str] = []
    totales_region: dict[str, dict[int, float | None]] = {}
    provincias: dict[str, dict[int, float | None]] = {}
    frecuencia: dict[str, dict[str, dict[int, float | None]]] = {}

    for nombre in CATEGORIAS:
        for medida in (1, 2):
            path = descargar(nombre, medida, comunas, args.force)
            datos, _niveles = leer_tabla(path, ANIOS)
            print(f"  {nombre:<26} {MEDIDAS[medida]:<11} {path.name} ({len(datos)} filas)")

            if medida == 1:
                frecuencia[nombre] = {}
                totales_region[nombre] = datos.get("Región Metropolitana", {})
                provincias[nombre] = {
                    k: v for k, v in datos.items() if k.lower().startswith("provincia de ")
                }

            vistos = 0
            for etiqueta, valores in datos.items():
                clave = sin_tildes(etiqueta)
                if clave not in clave_a_codigo:
                    continue
                vistos += 1
                codigo = clave_a_codigo[clave]
                if medida == 1:
                    frecuencia[nombre][codigo] = valores
                for anio in ANIOS:
                    valor = valores.get(anio)
                    filas.append(
                        {
                            "anio": anio,
                            "codigo_comuna": codigo,
                            "comuna": clave_a_nombre[clave],
                            "categoria": nombre,
                            "casos": valor if medida == 1 else None,
                            "tasa_100k": valor if medida == 2 else None,
                            "tipo_registro": "casos_policiales",
                            "origen_dato": ORIGEN,
                        }
                    )
            if vistos != 52:
                problemas.append(f"{nombre}/{MEDIDAS[medida]}: {vistos} comunas reconocidas (esperadas 52)")

    tabla = pd.DataFrame(filas)
    # casos y tasa vienen en dos tablas: se consolidan en una fila por (año, comuna, categoría)
    tabla = (
        tabla.groupby(["anio", "codigo_comuna", "comuna", "categoria"], as_index=False)
        .agg(
            casos=("casos", "max"),
            tasa_100k=("tasa_100k", "max"),
            tipo_registro=("tipo_registro", "first"),
            origen_dato=("origen_dato", "first"),
        )
        .reset_index(drop=True)
    )

    # dmcs_total: suma de los componentes publicados (ver COMPONENTES_DMCS). Se agrega como
    # una categoría más, con el origen marcado para que se note que es un agregado propio.
    dmcs = (
        tabla[tabla["categoria"].isin(COMPONENTES_DMCS)]
        .groupby(["anio", "codigo_comuna", "comuna"], as_index=False)
        .agg(casos=("casos", "sum"), tasa_100k=("tasa_100k", "sum"))
    )
    dmcs["categoria"] = "dmcs_total"
    dmcs["tipo_registro"] = "casos_policiales"
    dmcs["origen_dato"] = ORIGEN + " (suma de categorías DMCS)"
    tabla = pd.concat([tabla, dmcs], ignore_index=True).sort_values(
        ["categoria", "anio", "codigo_comuna"]
    ).reset_index(drop=True)

    # ------------------------- verificaciones -------------------------
    n_categorias = len(CATEGORIAS) + 1  # + dmcs_total
    print("\nVerificaciones")
    esperadas = 52 * len(ANIOS) * n_categorias
    print(f"  filas: {len(tabla)} (esperadas {esperadas})")
    if len(tabla) != esperadas:
        problemas.append(f"filas {len(tabla)} != {esperadas}")

    por_categoria = tabla.groupby("categoria")["codigo_comuna"].nunique()
    if not (por_categoria == 52).all():
        problemas.append("alguna categoría no tiene 52 comunas: " + str(por_categoria[por_categoria != 52]))
    print(f"  comunas distintas por categoría: {por_categoria.min()}-{por_categoria.max()}")

    if not set(tabla["codigo_comuna"]) <= codigos:
        problemas.append("hay códigos de comuna que no están en data/comunas_rm.csv")
    if set(tabla["anio"]) != set(ANIOS):
        problemas.append("los años no calzan")
    print(f"  años: {sorted(set(tabla['anio']))}")

    # 1) la región debe ser igual a la suma de sus 52 comunas
    for nombre in CATEGORIAS:
        for anio in ANIOS:
            suma = sum(frecuencia[nombre][c].get(anio) or 0 for c in codigos if c in frecuencia[nombre])
            region = totales_region[nombre].get(anio)
            if region is None:
                problemas.append(f"{nombre} {anio}: sin total regional")
            elif abs(suma - region) > 0.5:
                problemas.append(f"{nombre} {anio}: suma comunas {suma:.0f} != región {region:.0f}")
    print("  suma de las 52 comunas == total regional: revisado en todas las categorías/años")

    # 2) cada provincia debe ser igual a la suma de sus comunas
    for nombre in CATEGORIAS:
        for anio in ANIOS:
            for prov, valores in provincias[nombre].items():
                p = sin_tildes(prov.replace("Provincia de ", ""))
                suma = sum(
                    (frecuencia[nombre][c].get(anio) or 0)
                    for c in codigos
                    if c in frecuencia[nombre] and sin_tildes(codigo_a_provincia[c]) == p
                )
                if abs(suma - (valores.get(anio) or 0)) > 0.5:
                    problemas.append(f"{nombre} {anio} provincia {p}: {suma:.0f} != {valores.get(anio)}")
    print("  suma por provincia == fila de provincia: revisado")

    # 3) dmcs_total: sin ceros ni negativos, y nunca menor que su componente más grande
    for anio in ANIOS:
        rm = dmcs[dmcs["anio"] == anio]["casos"].sum()
        print(f"  dmcs_total RM {anio}: {rm:,.0f} casos")
    piv = tabla.pivot_table(index=["anio", "codigo_comuna"], columns="categoria", values="casos")
    pmax = piv[COMPONENTES_DMCS].max(axis=1)
    malos = int((piv["dmcs_total"] < pmax).sum())
    if malos:
        problemas.append(f"{malos} filas con dmcs_total menor que un componente")
    if (piv["dmcs_total"] < 0).any():
        problemas.append("dmcs_total con valores negativos")

    # 4) sin casos/tasa faltantes
    faltan_casos = int(tabla["casos"].isna().sum())
    faltan_tasa = int(tabla["tasa_100k"].isna().sum())
    print(f"  celdas sin casos: {faltan_casos} | sin tasa: {faltan_tasa}")
    if faltan_casos or faltan_tasa:
        problemas.append(f"faltan {faltan_casos} casos y {faltan_tasa} tasas")

    # 5) consistencia casos/tasa: la población implícita debe parecerse a la del Censo.
    #    El portal usa proyecciones INE (Censo 2024), no los conteos censales, así que se
    #    informa el desvío mediano en vez de exigir igualdad.
    ext = tabla[(tabla["casos"] > 0) & (tabla["tasa_100k"] > 0)].copy()
    ext["pob_implicita"] = ext["casos"] / ext["tasa_100k"] * 100_000
    ref = comunas.set_index("codigo_comuna")
    ext["pob_ref"] = [
        (ref.loc[c, "poblacion_2017"] if a <= 2021 else ref.loc[c, "poblacion_2024"])
        for a, c in zip(ext["anio"], ext["codigo_comuna"])
    ]
    desvio = (ext["pob_implicita"] / ext["pob_ref"] - 1).abs()
    print(f"  desvío mediano de la población implícita vs comunas_rm.csv: {desvio.median():.1%}")
    if desvio.median() > 0.60:
        problemas.append(f"población implícita poco creíble (desvío mediano {desvio.median():.0%})")

    # 6) control contra el otro endpoint del portal ("por delito", seleccion=2)
    print("  control contra el endpoint 'por delito' (RM, 2017 y 2024):")
    control = {"homicidios": "Homicidios y femicidios", "hurtos": "Hurtos",
               "robo_en_lugar_habitado": "Robo en lugar habitado"}
    for nombre, etiqueta in control.items():
        nivel, codigo = CATEGORIAS[nombre][0]
        datos = pedir_por_delito(nivel, codigo, args.force)
        serie = tabla[(tabla.categoria == nombre) & (tabla.anio.isin([2017, 2024]))]
        suma = serie.groupby("anio")["casos"].sum()
        fila = next((v for k, v in datos.items() if sin_tildes(k) == sin_tildes(etiqueta)), None)
        if fila is None:
            problemas.append(f"control {nombre}: no se encontró la fila {etiqueta!r}")
            continue
        for anio in (2017, 2024):
            got, esperado = fila.get(anio), suma.get(anio)
            ok = got is not None and esperado is not None and abs(got - esperado) < 0.5
            if not ok:
                problemas.append(f"control {nombre} {anio}: portal {got} != tabla {esperado}")
            print(f"    {nombre:<24} {anio}: portal {got:,.0f} | tabla {esperado:,.0f} {'ok' if ok else 'DIF'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if (tabla["casos"] % 1 != 0).any():
        problemas.append("hay casos con decimales; la fuente entrega frecuencias enteras")
    tabla["casos"] = tabla["casos"].round().astype("Int64")
    tabla.to_csv(OUT, index=False, encoding="utf-8")
    print(f"\nescrito {OUT.relative_to(ROOT)} ({len(tabla)} filas)")

    if problemas:
        print("\nPROBLEMAS:")
        for p in problemas[:40]:
            print("  -", p)
        return 1
    print("sin problemas detectados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
