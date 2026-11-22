"""Trazado de los ríos de la Región Metropolitana y las comunas por donde pasa cada uno.

Los cauces salen de las teselas vectoriales de OpenFreeMap (esquema OpenMapTiles, datos de OpenStreetMap,
ODbL): son las mismas que dibuja el mapa de la interfaz, y sirven cuando Overpass no responde. Cada tesela
se decodifica aquí mismo (formato Mapbox Vector Tile), sin dependencias.

Lee viz/public/datos/caudales.json (lo escribe `datos.dga.fetch_caudales`, que debe correr antes) y:
- escribe viz/public/geo/rios_rm.geojson: una línea por tramo, con `nombre`, `clase` y `estacion`;
- agrega a caudales.json la lista `cauces` (por cada río con nombre: comunas por donde pasa, de aguas
  arriba a aguas abajo, largo dentro de la región y estación que lo mide) y, a cada estación, `vivo`:
  la página de caudalrio.cl con su caudal en tiempo real (tomada del mapa del sitio, no de su API).

Uso (desde la raíz del repo):  python -m datos.dga.rios_teselas
Las teselas quedan en data/raw/dga/teselas/ (fuera de git); bórralas para refrescar.
"""

from __future__ import annotations

import datetime as dt
import gzip
import itertools
import json
import math
import re
import time
import unicodedata
import urllib.error
import urllib.request

from datos.comun import USER_AGENT
from datos.dga.fetch_caudales import (
    BBOX,
    JSON_OUT,
    OUT,
    RAW,
    RIOS_OUT,
    Comunas,
    dp_simplify,
    length_km,
)

TILEJSON = "https://tiles.openfreemap.org/planet"
SITEMAP_VIVO = "https://caudalrio.cl/sitemap.xml"
ZOOM = 12
ZOOM_ESTEROS = 13
RADIO_ESTEROS = 3  # teselas alrededor de cada estación de estero, al zoom de esteros
SIMPLIFY_DEG = 0.0005
TOL_UNION = 1.5e-4  # grados (~15 m): extremos de dos teselas vecinas que son el mismo punto
PASO_MUESTRA_KM = 0.25
MIN_KM_COMUNA = 0.8
MIN_KM_TRAMO = 0.4
ARTICULOS = {"de", "del", "la", "el", "los", "las", "san"}
# Cauces que la DGA y el mapa nombran con distinto tipo (clave de la estación → clave del mapa).
OTRA_CLAVE = {"estero puangue": "rio puangue"}


# --- nombres ------------------------------------------------------------------------------------


def clave_cauce(nombre: str) -> str:
    """«Quebrada de Ramón» y «Quebrada Ramon» son el mismo cauce."""
    plano = unicodedata.normalize("NFD", nombre).encode("ascii", "ignore").decode().lower()
    clave = " ".join(w for w in re.findall(r"[a-z0-9]+", plano) if w not in ARTICULOS)
    return OTRA_CLAVE.get(clave, clave)


# --- Mapbox Vector Tile -------------------------------------------------------------------------


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    n = shift = 0
    while True:
        b = buf[i]
        i += 1
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n, i
        shift += 7


def _campos(buf: bytes):
    """Campos de un mensaje protobuf: (número, tipo de cable, valor)."""
    i = 0
    while i < len(buf):
        key, i = _varint(buf, i)
        num, wire = key >> 3, key & 7
        if wire == 0:
            val, i = _varint(buf, i)
        elif wire == 2:
            n, i = _varint(buf, i)
            val, i = buf[i : i + n], i + n
        elif wire == 5:
            val, i = buf[i : i + 4], i + 4
        elif wire == 1:
            val, i = buf[i : i + 8], i + 8
        else:
            raise ValueError(f"tipo de cable {wire} no esperado")
        yield num, wire, val


def _empaquetados(buf: bytes) -> list[int]:
    out, i = [], 0
    while i < len(buf):
        v, i = _varint(buf, i)
        out.append(v)
    return out


def _zigzag(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


def lineas_de_capa(tile: bytes, capa: str) -> list[tuple[dict, list[list[tuple[int, int]]], int]]:
    """Líneas de una capa de la tesela: (propiedades de texto, líneas en unidades de tesela, extensión)."""
    out = []
    for num, _, layer in _campos(tile):
        if num != 3:
            continue
        nombre, keys, values, feats, extent = None, [], [], [], 4096
        for n, _, v in _campos(layer):
            if n == 1:
                nombre = v.decode("utf-8", "replace")
            elif n == 2:
                feats.append(v)
            elif n == 3:
                keys.append(v.decode("utf-8", "replace"))
            elif n == 4:
                texto = None
                for vn, vw, vv in _campos(v):
                    if vn == 1 and vw == 2:
                        texto = vv.decode("utf-8", "replace")
                values.append(texto)
            elif n == 5:
                extent = v
        if nombre != capa:
            continue
        for feat in feats:
            tags, tipo, geom = [], 0, []
            for n, _, v in _campos(feat):
                if n == 2:
                    tags = _empaquetados(v)
                elif n == 3:
                    tipo = v
                elif n == 4:
                    geom = _empaquetados(v)
            if tipo != 2:
                continue
            props = {
                keys[k]: values[val]
                for k, val in zip(tags[::2], tags[1::2])
                if values[val] is not None
            }
            lineas, actual, x, y, i = [], [], 0, 0, 0
            while i < len(geom):
                cmd, cuenta = geom[i] & 7, geom[i] >> 3
                i += 1
                if cmd == 7:
                    continue
                for _ in range(cuenta):
                    x += _zigzag(geom[i])
                    y += _zigzag(geom[i + 1])
                    i += 2
                    if cmd == 1:
                        if len(actual) > 1:
                            lineas.append(actual)
                        actual = [(x, y)]
                    else:
                        actual.append((x, y))
            if len(actual) > 1:
                lineas.append(actual)
            out.append((props, lineas, extent))
    return out


def recortar(linea: list[tuple[float, float]], lado: float) -> list[list[tuple[float, float]]]:
    """Parte de una línea dentro del cuadro [0, lado]² (las teselas traen un margen que se repite en la vecina)."""
    tramos, actual = [], []
    for (x0, y0), (x1, y1) in itertools.pairwise(linea):
        t0, t1, dx, dy = 0.0, 1.0, x1 - x0, y1 - y0
        fuera = False
        for p, q in ((-dx, x0), (dx, lado - x0), (-dy, y0), (dy, lado - y0)):
            if p == 0:
                if q < 0:
                    fuera = True
                    break
            else:
                r = q / p
                if p < 0:
                    t0 = max(t0, r)
                else:
                    t1 = min(t1, r)
        if fuera or t0 > t1:
            if len(actual) > 1:
                tramos.append(actual)
            actual = []
            continue
        a = (x0 + t0 * dx, y0 + t0 * dy)
        b = (x0 + t1 * dx, y0 + t1 * dy)
        if not actual or t0 > 0:
            if len(actual) > 1:
                tramos.append(actual)
            actual = [a]
        actual.append(b)
        if t1 < 1:
            tramos.append(actual)
            actual = []
    if len(actual) > 1:
        tramos.append(actual)
    return tramos


# --- teselas ------------------------------------------------------------------------------------


def tesela_de(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2**z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def a_lonlat(z: int, tx: int, ty: int, px: float, py: float, extent: int) -> tuple[float, float]:
    n = 2**z
    lon = (tx + px / extent) / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + py / extent) / n))))
    return lon, lat


def bajar(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def tesela(plantilla: str, z: int, x: int, y: int) -> bytes:
    ruta = RAW / "teselas" / str(z) / str(x) / f"{y}.pbf"
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        try:
            datos = bajar(plantilla.format(z=z, x=x, y=y))
        except urllib.error.HTTPError as e:
            if e.code not in (204, 404):
                raise
            datos = b""  # tesela sin datos
        ruta.write_bytes(datos)
        time.sleep(0.05)
    return ruta.read_bytes()


def cauces_de_teselas(
    plantilla: str, z: int, teselas: set[tuple[int, int]], quiere
) -> list[tuple[str, str, list]]:
    """(nombre, clase, línea lon/lat) de cada cauce con nombre que `quiere(nombre, clase)` acepta."""
    out = []
    for x, y in sorted(teselas):
        datos = tesela(plantilla, z, x, y)
        if not datos:
            continue
        for props, lineas, extent in lineas_de_capa(datos, "waterway"):
            nombre, clase = props.get("name"), props.get("class")
            if not nombre or clase not in ("river", "stream") or not quiere(nombre, clase):
                continue
            for linea in lineas:
                for tramo in recortar(linea, extent):
                    out.append(
                        (nombre, clase, [a_lonlat(z, x, y, px, py, extent) for px, py in tramo])
                    )
    return out


# --- unión, comunas -----------------------------------------------------------------------------


def unir(lineas: list[list], tol: float = TOL_UNION) -> list[list]:
    """Une líneas cuando el fin de una cae sobre el inicio de otra (con tolerancia), sin cambiar el sentido."""
    lineas = [list(x) for x in lineas]

    def cerca(a, b) -> bool:
        return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol

    cambio = True
    while cambio:
        cambio = False
        for i, a in enumerate(lineas):
            for j, b in enumerate(lineas):
                if i != j and cerca(a[-1], b[0]):
                    lineas[i] = a + b[1:]
                    del lineas[j]
                    cambio = True
                    break
            if cambio:
                break
    return lineas


def comunas_de(lineas: list[list], comunas: Comunas) -> tuple[list[str], float]:
    """Comunas que el cauce cruza o bordea, de aguas arriba a aguas abajo, y km dentro de la región.

    Los tramos no siempre se unen en una sola línea, así que el orden sale de proyectar cada punto sobre
    el sentido general del cauce (la suma de los vectores inicio→fin de sus tramos, que van aguas abajo).
    """
    km: dict[str, float] = {}
    pos: dict[str, float] = {}
    dx = sum(linea[-1][0] - linea[0][0] for linea in lineas)
    dy = sum(linea[-1][1] - linea[0][1] for linea in lineas)
    for linea in lineas:
        for p, q in itertools.pairwise(linea):
            largo = length_km([p, q])
            pasos = max(1, round(largo / PASO_MUESTRA_KM))
            for k in range(pasos):
                t = (k + 0.5) / pasos
                x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
                codigo = comunas.code_at(x, y)
                if codigo:
                    km[codigo] = km.get(codigo, 0.0) + largo / pasos
                    pos[codigo] = pos.get(codigo, 0.0) + (x * dx + y * dy) * largo / pasos
    orden = sorted((c for c in km if km[c] >= MIN_KM_COMUNA), key=lambda c: pos[c] / km[c])
    return orden, sum(km.values())


def recortar_a_region(linea: list, comunas: Comunas) -> list[list]:
    tramos, actual = [], []
    for p, q in itertools.pairwise(linea):
        if comunas.code_at((p[0] + q[0]) / 2, (p[1] + q[1]) / 2):
            actual = actual or [p]
            actual.append(q)
        elif actual:
            tramos.append(actual)
            actual = []
    if actual:
        tramos.append(actual)
    return tramos


def enlaces_vivo(xml: str) -> dict[str, str]:
    """Código de estación (sin el 0 inicial ni el dígito verificador) → página de la estación."""
    out = {}
    for url in re.findall(r"<loc>(https://caudalrio\.cl/caudal/[a-z0-9-]+)</loc>", xml):
        m = re.search(r"-0(\d{7})-[0-9k]$", url)
        if m:
            out[m.group(1)] = url
    return out


def main() -> None:
    caudales = json.loads(JSON_OUT.read_text(encoding="utf-8"))
    estaciones = caudales["estaciones"]
    comunas = Comunas.load()
    plantilla = json.loads(bajar(TILEJSON))["tiles"][0]

    sur, oeste, norte, este = BBOX
    x0, y0 = tesela_de(oeste, norte, ZOOM)
    x1, y1 = tesela_de(este, sur, ZOOM)
    todas = {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    brutos = cauces_de_teselas(plantilla, ZOOM, todas, lambda n, c: c == "river")

    # Esteros y quebradas con estación: solo aparecen a más zoom, así que se piden alrededor de la estación.
    claves_estacion = {clave_cauce(e["rio"]) for e in estaciones}
    ya = {clave_cauce(n) for n, _, _ in brutos}
    cerca: set[tuple[int, int]] = set()
    for e in estaciones:
        if clave_cauce(e["rio"]) in ya:
            continue
        cx, cy = tesela_de(e["lon"], e["lat"], ZOOM_ESTEROS)
        cerca |= {
            (cx + i, cy + j)
            for i in range(-RADIO_ESTEROS, RADIO_ESTEROS + 1)
            for j in range(-RADIO_ESTEROS, RADIO_ESTEROS + 1)
        }
    brutos += cauces_de_teselas(
        plantilla,
        ZOOM_ESTEROS,
        cerca,
        lambda n, c: clave_cauce(n) in claves_estacion and clave_cauce(n) not in ya,
    )

    mejor: dict[str, dict] = {}
    for e in sorted(estaciones, key=lambda e: -e["medio"]):
        mejor.setdefault(clave_cauce(e["rio"]), e)

    grupos: dict[str, dict] = {}
    for nombre, clase, linea in brutos:
        g = grupos.setdefault(clave_cauce(nombre), {"nombre": nombre, "clase": clase, "lineas": []})
        g["lineas"].append(linea)

    feats, cauces = [], []
    for clave, g in sorted(grupos.items()):
        dentro = [t for linea in unir(g["lineas"]) for t in recortar_a_region(linea, comunas)]
        dentro = [t for t in unir(dentro) if length_km(t) >= MIN_KM_TRAMO]
        if not dentro:
            continue
        codigos, largo = comunas_de(dentro, comunas)
        estacion = mejor.get(clave)
        if not codigos and not estacion:
            continue
        cauces.append(
            {
                "nombre": g["nombre"],
                "clase": g["clase"],
                "estacion": estacion["codigo"] if estacion else None,
                "comunas": codigos,
                "largo_km": round(largo, 1),
            }
        )
        for tramo in dentro:
            pts = [(round(x, 4), round(y, 4)) for x, y in dp_simplify(tramo, SIMPLIFY_DEG)]
            pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
            if len(pts) > 1:
                feats.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "nombre": g["nombre"],
                            "clase": g["clase"],
                            "estacion": estacion["codigo"] if estacion else None,
                        },
                        "geometry": {"type": "LineString", "coordinates": [list(p) for p in pts]},
                    }
                )

    RIOS_OUT.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": feats},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        vivo = enlaces_vivo(bajar(SITEMAP_VIVO).decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"Sin enlaces en vivo: {e}")
        vivo = {}
    for e in estaciones:
        e["vivo"] = vivo.get(e["codigo"])
    caudales["cauces"] = sorted(cauces, key=lambda c: -c["largo_km"])
    caudales["meta"]["cauces"] = "OpenStreetMap (ODbL), vía teselas de OpenFreeMap"
    JSON_OUT.write_text(
        json.dumps(caudales, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )

    ruta_manifiesto = OUT / "manifest.json"
    manifiesto = (
        json.loads(ruta_manifiesto.read_text(encoding="utf-8")) if ruta_manifiesto.exists() else {}
    )
    manifiesto["rios_teselas"] = {
        "url": plantilla,
        "descargado": dt.date.today().isoformat(),
        "zoom": ZOOM,
        "zoom_esteros": ZOOM_ESTEROS,
        "teselas": len(todas) + len(cerca),
        "licencia": "ODbL, © OpenStreetMap contributors",
        "enlaces_vivo": SITEMAP_VIVO,
    }
    ruta_manifiesto.write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    con = sum(1 for c in cauces if c["estacion"])
    print(
        f"{len(cauces)} cauces ({con} con estación), {len(feats)} tramos, {RIOS_OUT.stat().st_size} bytes"
    )
    for c in cauces:
        if c["estacion"]:
            print(f"  {c['nombre']}: {c['largo_km']} km, {len(c['comunas'])} comunas")
    sin = sorted(claves_estacion - {clave_cauce(c["nombre"]) for c in cauces})
    if sin:
        print("Estaciones sin cauce en las teselas:", ", ".join(sin))


if __name__ == "__main__":
    main()
