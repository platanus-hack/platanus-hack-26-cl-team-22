# Decretos de escasez hídrica en la Región Metropolitana, 2008–2023

Descarga realizada el 2026-11-21 con `.venv/bin/python -m datos.dga.fetch_decretos`.
Fuente: Dirección General de Aguas (MOP), planilla histórica enlazada desde
https://dga.mop.gob.cl/derechos-de-agua/proteccion-de-las-fuentes/decretos-de-escasez-2/
(el nombre del archivo lleva fecha; el script lo lee de la página en cada corrida).
`manifest.json` guarda URL, fecha y SHA-256.

`decretos_escasez_rm.csv`: una fila por decreto y comuna. Columnas `anio`, `decreto`,
`fecha_decreto`, `fecha_caducidad`, `codigo_comuna` (CUT), `comuna`, `por_provincia` (1 si el
decreto nombra solo la provincia y se expandió a sus comunas) y `texto_original`.

- 79 decretos de la RM cubren 24 comunas. Las 28 comunas urbanas de la provincia de Santiago
  (Santiago, Ñuñoa, Providencia, Maipú, La Florida, ...) nunca tuvieron decreto.
- Último decreto de la RM: N°251 del 20-12-2023 (Tiltil).
- Se descartan 2 filas rotuladas «Metropolitana» que hablan de otras regiones: N°54/2020
  (O'Higgins) y N°100/2020 (Valparaíso). Quedan listadas en el manifiesto.
- El texto mezcla cuencas, provincias y comunas: la regla de lectura está en el script.

# Caudales medios mensuales de ríos de la RM, 1980–2017

Descarga realizada el 2026-11-21 con `python -m datos.dga.fetch_caudales` (solo biblioteca estándar).
Fuente: Dirección General de Aguas (MOP), caudales medios mensuales (m³/s) compilados por (CR)2,
versión 2018 (809 estaciones del país, feb-1913 a feb-2018), licencia CC0.
Página: https://www.cr2.cl/datos-de-caudales/ (el enlace del zip lleva un token, así que el script lo
lee de la página en cada corrida; el sitio exige un User-Agent de navegador). `manifest.json` guarda
URL, fecha y SHA-256 del zip y de la página, y la consulta Overpass en la clave `caudales_rm`.
Correr `fetch_decretos` reescribe `manifest.json` sin estas entradas: correr `fetch_caudales` después.

Archivos:
- `caudales_rm_mensual.csv`: `codigo_estacion,anio,mes,caudal_m3s`, solo valores válidos desde 1980-01.
- `estaciones_caudal_rm.csv`: metadatos de las estaciones conservadas, con `codigo_comuna` (CUT).
- `viz/public/datos/caudales.json`: estaciones con serie anual, régimen mensual e indicadores
  (formato en la cabecera de `datos/dga/fetch_caudales.py`).

Reglas de selección (14 de 809 estaciones):
- Coordenadas dentro de uno de los 52 polígonos de `viz/public/geo/comunas_rm.geojson` (punto en
  polígono; la comuna es la del polígono, no la que declara la DGA).
- Nombre que empieza con Río, Estero o Quebrada (se descartan «Canal …» y otras derivaciones).
- Al menos 15 años válidos en 1980–2017 y 4 en 2010–2017. Año válido: 10 meses o más con dato;
  caudal anual = promedio de los meses disponibles.

Indicadores por estación: `medio` (promedio de años válidos), `base` (1980–2009, nulo con menos de
10 años), `sequia` (2010–2017), `cambio` (% de `sequia` frente a `base`), `regimen` (promedio de cada
mes calendario sobre todos los meses con dato) y `cv` (desviación estándar poblacional / promedio de
los valores mensuales).

Límites:
- La compilación termina en feb-2018: no cubre la sequía 2018–2024.
- Una estación aguas abajo de bocatomas mide caudal ya intervenido; la serie es de caudal, no de
  caudal natural. Los años con menos de 10 meses quedan en nulo, no se interpolan.
- Solo 14 estaciones cumplen las reglas y ninguna está en la zona urbana de la provincia de Santiago
  salvo el Mapocho en Rinconada de Maipú (Maipú) y Quebrada Ramón (Las Condes).

## Ríos (OpenStreetMap)

`viz/public/geo/rios_rm.geojson`: líneas `waterway=river` del bbox de la RM (S -34.35, O -71.75,
N -32.85, E -69.70) y `waterway=stream` con el nombre de un curso de las estaciones conservadas, vía
Overpass API (`overpass-api.de`, con `overpass.kumi.systems` de respaldo). © OpenStreetMap contributors,
licencia ODbL. Las vías del mismo nombre se unen donde se tocan, conservando el sentido del flujo
(el orden de OSM); se recortan a los tramos cuyo punto medio cae en alguna comuna de la RM, se
simplifican (Douglas-Peucker, 0.0008°), se redondean a 4 decimales y se descartan los tramos sin
nombre de menos de 2 km. `estacion` es la estación conservada con mayor `medio` cuyo curso coincide
con el nombre (sin acentos ni «Río»), o `null`.
Estado: la corrida del 2026-11-21 no pudo conectarse a Overpass (tiempo de espera agotado en ambos
servidores), por lo que este archivo aún no se generó; el manifiesto lo registra en `overpass`.

## Trazado de los ríos y comunas por donde pasan

`python -m datos.dga.rios_teselas` (correr después de `fetch_caudales`, que reescribe `caudales.json`).
Overpass no respondía al momento de la descarga, así que los cauces se leen de las teselas vectoriales de
OpenFreeMap (esquema OpenMapTiles, datos © OpenStreetMap contributors, ODbL): zoom 12 para los ríos de toda la
región y zoom 13 alrededor de las estaciones de esteros y quebradas. Escribe `viz/public/geo/rios_rm.geojson` y
agrega a `viz/public/datos/caudales.json`:

- `cauces`: por cada río con nombre, las comunas que cruza o bordea (al menos 0,8 km dentro de la comuna),
  ordenadas de aguas arriba a aguas abajo, los km dentro de la región y la estación que lo mide.
- `vivo` en cada estación: la página de caudalrio.cl con su caudal en tiempo real, tomada del mapa del sitio
  (`sitemap.xml`). No se consulta su API (su `robots.txt` lo pide) ni el portal de la DGA.

Límites: un río que hace de límite entre dos comunas cuenta para las dos; el orden sale de proyectar los tramos
sobre el sentido general del cauce, no de una red hidrográfica; el nombre del mapa y el de la estación se
emparejan sin tildes ni artículos, con una excepción escrita a mano (la DGA dice «Estero Puangue»; el mapa,
«Río Puangue»).
