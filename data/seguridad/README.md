# Seguridad: delitos por comuna y año (CEAD)

Casos policiales y tasas cada 100.000 habitantes por comuna de la Región Metropolitana,
2017 a 2024, para las 52 comunas de `data/comunas_rm.csv`.

## Fuente

- **Organismo**: Centro de Estudios y Análisis del Delito (CEAD), Subsecretaría de
  Prevención del Delito, Ministerio de Seguridad Pública.
- **Portal**: <https://cead.minsegpublica.gob.cl/estadisticas-delictuales/>
  (el histórico `cead.spd.gov.cl` ya no resuelve por DNS).
- **Endpoint que usa el propio portal** (formulario "Descargar Excel"):
  `POST https://cead.minsegpublica.gob.cl/wp-content/themes/gobcl-wp-master/data/get_estadisticas_delictuales.php`
- **Fecha de descarga**: 2026-11-21.
- **Cobertura pedida al portal**: región 13 (Metropolitana), comunas de
  `data/comunas_rm.csv`, años 2017 a 2024, `seleccion=1` (unidad territorial),
  `tipoVal=1,2` (casos policiales).

Los archivos crudos, tal como los devuelve el portal (tablas HTML con extensión `.xls`),
quedan en `data/raw/seguridad/` (`cead_<categoria>_frecuencia.xls` y
`cead_<categoria>_tasa.xls`). No se ejecuta nada descargado: se parsean como HTML.

## Definiciones (según el portal)

- **Casos policiales** (`tipo_registro = casos_policiales`): denuncias que la comunidad
  realiza en unidades policiales **más** las detenciones por delitos flagrantes. Es el
  indicador "delitos conocidos por la policía". No son sentencias ni denuncias puras.
- **Frecuencia**: número de casos del período.
- **Tasa cada 100.000 habitantes**: casos del período divididos por la población de
  referencia y multiplicados por 100.000. El portal la calcula con la **población oficial
  proyectada por el INE vigente (Censo 2024)**, aplicada a toda la serie. Por eso
  `casos / tasa_100k * 100000` no coincide exactamente con la población censal de
  `data/comunas_rm.csv` (desvío mediano ~10 %).
- Las categorías son la agrupación vigente del portal (7 familias, 22 grupos,
  45 subgrupos), aplicada a todos los años de la serie.

## Categorías incluidas

| `categoria` | Qué es (etiqueta del portal) | Código consultado |
|---|---|---|
| `dmcs_total` | **Agregado propio**: suma de los componentes DMCS listados abajo. El portal no entrega esta fila; ver "Vacíos conocidos". | — |
| `homicidios` | Homicidios y femicidios | grupo 101 |
| `lesiones` | Lesiones graves o gravísimas + menos graves + leves | grupos 103, 104, 105 |
| `violaciones` | Violaciones | subgrupo 10201 |
| `delitos_sexuales` | Violaciones y otros delitos sexuales | grupo 102 |
| `robo_con_violencia` | Robos con violencia o intimidación (incluye robo violento de vehículo motorizado) | grupo 201 |
| `robo_por_sorpresa` | Robo por sorpresa | subgrupo 20201 |
| `robo_en_lugar_habitado` | Robo en lugar habitado | subgrupo 60101 |
| `robo_en_lugar_no_habitado` | Robo en lugar no habitado | subgrupo 60102 |
| `robo_de_vehiculo` | Robo de vehículo motorizado | subgrupo 60201 |
| `robo_objetos_de_vehiculo` | Robo de objetos de o desde vehículo | subgrupo 60202 |
| `otros_robos_con_fuerza` | Otros robos con fuerza en las cosas | subgrupo 60301 |
| `hurtos` | Hurtos | subgrupo 60401 |
| `violencia_intrafamiliar` | Violencia intrafamiliar | grupo 301 |
| `drogas` | Crímenes y simples delitos ley de drogas | grupo 401 |
| `armas` | Crímenes y simples delitos ley de armas | grupo 501 |
| `incivilidades` | Amenaza falta o riña, consumo en vía pública, daños, desórdenes, otras | familia 7 |

`dmcs_total` = `homicidios` + `lesiones` + `violaciones` + `robo_con_violencia` +
`robo_por_sorpresa` + `robo_en_lugar_habitado` + `robo_en_lugar_no_habitado` +
`robo_de_vehiculo` + `otros_robos_con_fuerza` + `hurtos` + `violencia_intrafamiliar`.

## Columnas de `delitos_comuna_anio.csv`

`anio`, `codigo_comuna` (5 dígitos, igual que `data/comunas_rm.csv`), `comuna`,
`categoria`, `casos` (entero), `tasa_100k`, `tipo_registro`, `origen_dato`.

7.072 filas = 17 categorías × 52 comunas × 8 años, sin celdas vacías.

## Reproducir

```bash
.venv/Scripts/python datos/seguridad/build_seguridad.py          # usa la caché de data/raw/seguridad
.venv/Scripts/python datos/seguridad/build_seguridad.py --force  # vuelve a descargar todo
```

El script hace 32 descargas secuenciales (2 s de pausa), verifica y escribe el CSV.
Comprueba: 52 comunas por categoría y año, códigos contra `comunas_rm.csv`, que la suma
de las 52 comunas iguale la fila regional y la provincial, y que 3 categorías
(homicidios, hurtos, robo en lugar habitado) coincidan con el otro reporte del portal
("por delito", `seleccion=2`).

## Vacíos conocidos

- **`dmcs_total` no es una fila del portal.** El portal no expone un agregado DMCS en su
  herramienta interactiva; devuelve ceros si se mezclan grupos y subgrupos en una misma
  consulta. Se construye sumando filas publicadas por separado. La composición sigue la
  clasificación DMCS tradicional del CEAD (el portal declara "2 grupos y 13 subgrupos"),
  pero **el listado exacto de esos 13 subgrupos no está publicado en el portal**: la
  selección usada está en la tabla de arriba y en `COMPONENTES_DMCS` del script. Si se
  necesita el DMCS oficial exacto, hay que contrastarlo con una publicación del CEAD.
- **`robo_objetos_de_vehiculo` queda fuera de `dmcs_total`** (la clasificación tradicional
  no lo cuenta como categoría DMCS aparte). Sí está disponible como fila propia.
- **Homicidios**: el propio portal advierte que sus cifras son preliminares y que la cifra
  oficial la publica el Centro para la Prevención de Homicidios y Delitos Violentos.
  `homicidios` incluye femicidios (grupo 101).
- **Series anteriores a 2017** existen en el portal (desde 2005) pero no se descargaron.
  2025 y 2026 también están en el portal; 2026 es un año parcial y no se incluyó.
- **Sin datos de victimización (ENUSC)**: este entregable es solo casos policiales.
  "Denuncias", "detenciones" y "aprehendidos" son otras opciones del portal y no se
  descargaron.
- **Población**: las tasas usan proyecciones INE posteriores al Censo 2024 aplicadas
  retroactivamente, así que pueden diferir de tasas publicadas antes de 2024.
