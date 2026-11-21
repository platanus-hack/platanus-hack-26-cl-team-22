# PM2.5 diario, Región Metropolitana (SINCA / MACAM), 2017-2024

Descarga realizada el 2026-11-21.

## Fuente

- Listado de estaciones: https://sinca.mma.gob.cl/index.php/region/index/id/M
- Ficha por estación (comuna, coordenadas UTM, enlace a la serie): `https://sinca.mma.gob.cl/index.php/estacion/index/id/<id>`
- Serie diaria PM2.5 (CSV, `;` como separador y `,` decimal):
  `https://sinca.mma.gob.cl/cgi-bin/APUB-MMA/apub.tsindico2.cgi?outtype=xcl&macro=./RM/<codigo>/Cal/PM25//PM25.diario.diario.ic&from=170101&to=250101&path=/usr/airviro/data/CONAMA/&lang=esp&rsrc=&macropath=`
  (`to` es exclusivo; fechas YYMMDD). El CSV trae tres columnas: registros validados, preliminares y no validados.
- No hay API documentada; es el mismo endpoint que usa el botón de descarga de SINCA.

## Archivos

- `pm25_diario.csv`: fecha, estacion_id, estacion, pm25 (µg/m³), estado (`validado` | `preliminar` | `no_validado`). Por día se usa validado si existe; si no, preliminar; si no, no validado.
- `estaciones.csv`: estación, comuna, lat/lon, primera/última fecha con dato y % de días con dato en 2017-2024.
- `pm25_mensual.csv`, `pm25_anual.csv`: media por estación y período, con `dias_validos`. La media queda vacía si hay menos de 75% de días. El anual incluye media de invierno (mayo-agosto, 123 días, mismo umbral).
- Crudos tal cual los sirve SINCA: `data/raw/sinca/<codigo>_<estacion>.csv` y `data/raw/sinca/pages/` (HTML de listado y fichas).

## Cómo reejecutar

```bash
.venv/Scripts/python -I datos/aire/fetch_sinca.py
```

Usa caché: no vuelve a descargar lo que ya está en `data/raw/sinca/`. Para refrescar, borrar esa carpeta. Requiere `requests` y `pandas`.

## Vacíos y advertencias conocidas

- Estaciones sin cobertura útil: Cerrillos I (D16, cierra 2017-01-11), Quilicura I (D29, cerró en 2016), Cerrillos (D31, datos hasta 2021-07-14), Independencia (D11, datos hasta 2021-07-29), Cerrillos II (D35, desde 2022-04-12). Cerrillos y Cerrillos II son reemplazos sucesivos en la misma comuna, con un hueco entre 2021-07 y 2022-04. La ficha de SINCA declara fin de datos en 2022 para Independencia y Cerrillos, pero el CSV no trae nada posterior a 2021-07.
- La Pintana no mide PM2.5 (se omite).
- Los valores validados vienen redondeados a enteros (97% son enteros); los preliminares traen decimales. Hay 12 días con pm25 = 0 (La Florida, Parque O'Higgins, Quilicura), probablemente fallas, no se corrigieron.
- Los preliminares/no validados (p. ej. Pudahuel hasta 2018-05-17, parte de La Florida y Cerrillos) pueden cambiar cuando SINCA los valide.
- Las coordenadas se convirtieron de UTM huso 19S a lat/lon asumiendo datum WGS84 (SINCA no lo declara); error esperado de metros.
- Pudahuel, El Bosque, La Florida y Las Condes figuran "(Acreditada)" en SINCA; el nombre se conserva tal cual.
