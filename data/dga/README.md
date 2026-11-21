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
