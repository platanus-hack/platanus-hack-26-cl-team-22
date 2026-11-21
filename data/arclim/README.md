# Proyecciones climáticas por comuna (ARClim), Región Metropolitana

Descarga realizada el 2026-11-21 con `.venv/bin/python -m datos.arclim.fetch_arclim`.
Fuente: ARClim, Atlas de Riesgos Climáticos, Ministerio del Medio Ambiente
(https://arclim.mma.gob.cl), API pública documentada en
https://arclim.mma.gob.cl/media/learning/API_ARClim.pdf (diciembre 2025).
`manifest.json` guarda la URL, la fecha y el SHA-256 de cada una de las 1.041 respuestas.

Son **insumos** de la simulación, no resultados: el motor calcula sus propios índices de riesgo.

## Series por corrida de modelo climático

`series_{indicador}_{escenario}.csv.gz`: una fila por comuna y corrida de modelo climático
(GCM), una columna por año de 1970 a 2069. Columnas: `codigo_comuna` (CUT), `comuna`, `gcm`,
`corrida`, `nombre` y los años. Escenarios: `ssp245` (SSP2-4,5) y `ssp585` (SSP5-8,5).

Cada réplica de la simulación puede sortear una corrida: la incertidumbre climática sale de
modelos reales, no de una banda inventada.

| Indicador | Para qué | Corridas (ssp245 / ssp585) | Santiago 1991–2020 → 2041–2060 (ssp245) |
|---|---|---|---|
| `pr_sum` | Precipitación anual (mm): oferta de agua | 46 / 42 | 337,5 → 317,8 |
| `spi` | Índice estandarizado de precipitación | 46 / 42 | 0,0 → −0,2 |
| `drought_periods` | Frecuencia de sequía (%) | 46 / 42 | 32,5 → 38,6 |
| `eto_mean` | Evapotranspiración potencial (mm/día): demanda de agua | 10 / 9 | 2,2 → 2,4 |
| `maximum_daily_precipitation` | Precipitación máxima diaria (mm): inundación | 46 / 42 | 39,5 → 38,8 |
| `days_over_50mm` | Días sobre 50 mm: inundación | 46 / 42 | 0,2 → 0,2 |
| `hot_days` | Días sobre 30 °C: enfriamiento de centros de datos | 20 / 20 | 71,0 → 107,6 |
| `degdays_above_25` | Grados-día sobre 25 °C: demanda de enfriamiento | 20 / 20 | 381,7 → 503,5 |
| `degdays_below_17_heating` | Grados-día de calefacción: emisiones de leña | 20 / 20 | 1.720,6 → 1.506,1 |
| `rsds_mean` | Radiación solar media (W/m²): potencial solar | 19 / 17 | 209,0 → 209,4 |

**Son salidas de modelos, con sesgo.** Por ejemplo, la precipitación histórica modelada en
Santiago queda sobre lo observado. Usar cambios respecto de 1991–2020 de la misma corrida,
no niveles absolutos.

**`spi` tiene huecos.** Los archivos `series_spi_*` traen 8.958 celdas vacías (corrida × año),
repartidas en 26 modelos climáticos y en todas las comunas; vienen así de la API. Al muestrear
una corrida por réplica hay que saltar los años vacíos o elegir otra corrida.

## Componentes de riesgo de ARClim

`componentes_comuna.csv`: amenaza, exposición, vulnerabilidad y riesgo que ARClim publica por
comuna (presente 1980–2010, futuro 2035–2065 y cambio). Celda vacía = ARClim no la calcula
para esa comuna.

| Tema | Columnas | Comunas con dato |
|---|---|---|
| Inundación urbana (período de retorno 10 años) | `ind_*_inundaciones_*` | 41 de 52 |
| Sequía hidrológica combinada | `*_sequia_combinada*` | **9 de 52** |
| Seguridad hídrica urbana | `asentamientos_ind_*_aguaurb_*` | 51–52 de 52 |
| Generación solar | `energia_solar_*` | 52 de 52 |

`energia_solar_amen` aparece en el mapa del atlas, pero la API responde error 500 para ella
(2026-11-21); se dejó fuera.
