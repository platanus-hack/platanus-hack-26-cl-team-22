# Licitaciones públicas de Mercado Público (ChileCompra), Región Metropolitana

Ingesta reproducible de licitaciones mensuales publicadas en los **Datos Abiertos de ChileCompra** para las 52 comunas de la Región Metropolitana (`data/comunas_rm.csv`).

> **Estado actual en el repo:** descargado y procesado el **2026-11-21** para todo el año **2024 (`2024-01` a `2024-12`)**: 12 archivos ZIP (~270 MB) versionados con **Git LFS** en `data/raw/licitaciones/` (`2024-1.zip` … `2024-12.zip`), que produjeron `681.828` líneas RM (sobre `2.512.286` filas totales), **52/52 comunas** en `resumen_comuna_anio.csv`, `307` filas en `resumen_sector_comuna.csv` y `5` montos extremos filtrados (`manifest.json`).

## Fuente oficial

- **Repositorio:** Datos Abiertos de ChileCompra (Azure Blob Storage).
- **Plantilla de descarga:** `https://transparenciachc.blob.core.windows.net/lic-da/{year}-{month}.zip` (mes sin cero inicial: `2024-1.zip` … `2024-12.zip`).
- **Formato crudo:** archivos `lic_*.csv` dentro del ZIP, codificación `latin-1`, separados por `;`, con una fila por **ítem de línea** (`CodigoExterno` se repite cuando una licitación tiene múltiples líneas).
- **Enriquecimiento opcional por ficha:** `https://api.licitalab.cl/free/tender/{tender_id}` mediante `datos/licitaciones/enriquecer_ficha.py` (tope 9 req/min, solo para inspección puntual; nunca para descarga masiva).

## Cómo generar las tablas limpias

```bash
make licitaciones
# equivalente explícito:
.venv/bin/python -m datos.licitaciones.fetch_licitaciones --desde 2024-01 --hasta 2024-12
```

Los archivos ZIP originales (`2024-1.zip` … `2024-12.zip`) se guardan en `data/raw/licitaciones/` mediante **Git LFS** (`.gitattributes` y `.gitignore`) y `manifest.json` registra la URL, fecha de descarga, tamaño y SHA-256 de cada archivo.

## Tablas generadas

### `resumen_comuna_anio.csv`

Una fila por `(codigo_comuna, anio)` con métricas deduplicadas a nivel de licitación (`CodigoExterno`):

| Columna | Descripción |
|---|---|
| `codigo_comuna` | Código CUT oficial de 5 dígitos (`data/comunas_rm.csv`) |
| `anio` | Año de publicación (respaldo: adjudicación o cierre) |
| `total_licitaciones` | Licitaciones únicas del municipio/unidad en la comuna y año |
| `adjudicadas` | Licitaciones en estado adjudicado (`CodigoEstado = 8` o texto `Adjudicada`) |
| `fallidas` | Licitaciones desiertas, revocadas o suspendidas (`7`, `18`, `19`) |
| `cerradas` | `adjudicadas + fallidas` (denominador de la tasa de adjudicación) |
| `tasa_adjudicacion` | `adjudicadas / cerradas` (vacío si `cerradas = 0`) |
| `mediana_dias_pub_cierre` | Mediana de días entre publicación y cierre |
| `mediana_dias_pub_adj` | Mediana de días entre publicación y adjudicación |
| `mediana_oferentes` | Mediana de oferentes participantes |
| `proporcion_oferente_unico` | Fracción de licitaciones con exactamente 1 oferente |
| `monto_estimado_clp` | Suma deduplicada de `MontoEstimado` (excluyendo errores extremos > $1 billón) |
| `monto_adjudicado_clp` | Suma de `MontoLineaAdjudica` por línea (excluyendo outliers > $1 billón) |
| `total_reclamos` | Suma deduplicada de `CantidadReclamos` |

### `resumen_sector_comuna.csv`

Una fila por `(codigo_comuna, sector)` clasificada por palabras clave determinísticas en título, descripción y producto (`agua`, `energia`, `aire_calefaccion`, `seguridad`, `infraestructura`, `otros`).

### `manifest.json`

Metadatos de trazabilidad: URLs, hashes SHA-256 y conteos diagnósticos (`total_filas`, `filas_rm`, `filas_sin_comuna_rm`, `outliers_monto_filtrados`).

## Reglas y límites conocidos

- **Deduplicación por `CodigoExterno`:** los estados, fechas, oferentes, reclamos y `MontoEstimado` se toman una sola vez por licitación; solo `MontoLineaAdjudica` se suma entre ítems.
- **Emparejamiento conservador de comunas:** se asigna `codigo_comuna` solo si `ComunaUnidad` coincide con una de las 52 comunas RM (incluyendo normalización de `"Til Til"` / `"Til-Til"` → `"Tiltil"`, código `13303`) o si `NombreOrganismo` corresponde explícitamente a `Municipalidad de <comuna>`. Los organismos nacionales sin comuna específica quedan fuera (`filas_sin_comuna_rm`) para no inflar artificialmente a Santiago (`13101`).
- **Filtro de montos extremos y fechas centinela:** valores mayores a `$10^{12}` CLP y fechas anteriores a `2000-01-01` se excluyen automáticamente.
- **Contador `CantidadReclamos`:** en los CSV mensuales de ChileCompra este campo refleja un contador acumulado del organismo repetido en sus licitaciones (no reclamos exclusivos del proceso puntual), por lo que `total_reclamos` sirve solo como señal relativa bruta y no como conteo neto de reclamos del año.
- **Advertencia de lectura:** una baja tasa de adjudicación o licitación con 1 oferente es una señal estadística operativa, **no** prueba de irregularidad por sí sola.
