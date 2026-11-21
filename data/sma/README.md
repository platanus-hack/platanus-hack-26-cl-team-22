# Procesos sancionatorios de la SMA en la Región Metropolitana, 2013–2026

Descarga realizada el 2026-11-21 con `.venv/bin/python -m datos.sma.fetch_sancionatorios`.
Fuente: Superintendencia del Medio Ambiente, datos abiertos de SNIFA
(https://snifa.sma.gob.cl/DatosAbiertos), archivo `Sancionatorios.csv` en una carpeta pública
de Google Drive que se regenera cada día. `manifest.json` guarda URL, fecha y SHA-256.

`procesos_rm.csv`: 1.000 filas, 996 procesos, 51 comunas (María Pinto no tiene procesos).
Una fila = un proceso × unidad fiscalizable. Columnas: `codigo_comuna` (CUT), `comuna`, tipo
y estado del proceso, fechas de inicio y término (ISO), multa total en UTA (vacía si no hubo
multa), unidad fiscalizada, categoría económica, coordenadas y enlace a la ficha en SNIFA.

Las sanciones firmes solo se publican como PDF anuales; no están incluidas.

**`MultaTotalUTA` no siempre es una multa impuesta.** Tiene valor en 429 filas: 336 están en
estado "Terminado - Sanción", pero 88 siguen "En curso" y 5 están en programa de cumplimiento.
En esas 93 el monto es propuesto o provisional. Para contar multas aplicadas, filtrar por
`ProcesoSancionEstado == "Terminado - Sanción"`.
