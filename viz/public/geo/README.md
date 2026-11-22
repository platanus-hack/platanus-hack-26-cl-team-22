# Comunas de la Región Metropolitana (GeoJSON)

Archivo: `comunas_rm.geojson` (52 polígonos, una Feature por comuna, EPSG:4326 lon/lat, ~348 KB).
Propiedades: `codigo` (CUT comunal, 5 dígitos), `nombre`, `provincia`.

## Fuente

- Producto: División Político Administrativa (DPA) 2023, cartografía de comunas (`COMUNAS_v1.shp`).
- URL de descarga: https://ide.subdere.gov.cl/descargas/SHP/Limite_DPA_03082023.rar
  (página de referencia: https://www.subdere.gov.cl/node/82960)
- Publica: Subsecretaría de Desarrollo Regional y Administrativo (SUBDERE), a través del SNIT / Infraestructura de Datos Geoespaciales (IDE Chile).
- Licencia / términos: la página de descarga no declara licencia ni términos de uso. Es información pública del Estado de Chile; confirmar antes de uso comercial o redistribución.
- Fecha de descarga: 2026-11-21.
- Original sin modificar: `data/raw/geo/Limite_DPA_03082023.rar` (SHA-256 `4c8dd01ca4ca7d8b111dac78b88cc8ac64c1af7b8ebe0c85a21eaab337ae3fd3`).

## Cambios aplicados

1. Filtrado de las 345 comunas del país a las 52 de la Región Metropolitana (`CUT_REG = 13`).
2. Sistema de referencia: el shapefile está en GCS SIRGAS-Chile (grados, GRS80). Se trata como WGS84 (diferencia de ~1 m).
3. Reparación de geometrías inválidas (si las hubiera) con `make_valid`, y simplificación con tolerancia 0.0001° (~11 m), preservando topología.
4. Coordenadas redondeadas a 5 decimales. Cambio de área máximo respecto al original: 0.14 %.

Script: `datos/geo/build_comunas.py` (ver instrucciones de uso en su cabecera).

## Ríos

Archivo: `rios_rm.geojson` (LineString, orden de los vértices en el sentido del flujo; propiedades
`nombre`, `clase` y `estacion`). Fuente: OpenStreetMap vía Overpass API, © OpenStreetMap
contributors, licencia ODbL. Detalle y reglas en `data/dga/README.md`. Script:
`datos/dga/fetch_caudales.py`.
