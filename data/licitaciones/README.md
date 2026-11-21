# Licitaciones públicas de Mercado Público (ChileCompra), Región Metropolitana

Ingesta reproducible de licitaciones mensuales publicadas en los **Datos Abiertos de ChileCompra** para las 52 comunas de la Región Metropolitana (`data/comunas_rm.csv`).

> **Estado actual en el repo:** descargado y procesado el **2026-11-21** para todo el año **2024 (`2024-01` a `2024-12`)**: 12 archivos ZIP (~270 MB) versionados con **Git LFS** en `data/raw/licitaciones/` (`2024-1.zip` … `2024-12.zip`), que produjeron `236.576` líneas de compras municipales de la RM (sobre `2.512.286` filas totales), **52/52 comunas** en `resumen_comuna_anio.csv`, `292` filas en `resumen_sector_comuna.csv` y `5` montos extremos filtrados (`manifest.json`).

## Fuente oficial

- **Repositorio:** Datos Abiertos de ChileCompra (Azure Blob Storage).
- **Plantilla de descarga:** `https://transparenciachc.blob.core.windows.net/lic-da/{year}-{month}.zip` (mes sin cero inicial: `2024-1.zip` … `2024-12.zip`).
- **Formato crudo:** archivos `lic_*.csv` dentro del ZIP, codificación `latin-1`, separados por `;`, con una fila por **ítem de línea** (`CodigoExterno` se repite cuando una licitación tiene múltiples líneas).

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

### `resumen_sector_comuna.csv`

Una fila por `(codigo_comuna, sector)` clasificada por palabras clave determinísticas en título, descripción y producto (`agua`, `energia`, `aire_calefaccion`, `seguridad`, `infraestructura`, `otros`).

### `manifest.json`

Metadatos de trazabilidad: URLs, hashes SHA-256 y conteos diagnósticos (`total_filas`, `filas_rm`, `filas_sin_comuna_rm`, `outliers_monto_filtrados`).

## Reglas y límites conocidos

- **Deduplicación por `CodigoExterno`:** los estados, fechas, oferentes y `MontoEstimado` se toman una sola vez por licitación; solo `MontoLineaAdjudica` se suma entre ítems.
- **Solo compras municipales:** se asigna `codigo_comuna` solo si `NombreOrganismo` es `Municipalidad de <comuna>` (con variantes «I. Municipalidad», «Ilustre Municipalidad» y la normalización `"Til Til"` → `"Tiltil"`, `13303`). La ubicación de la unidad compradora (`ComunaUnidad`) se ignora a propósito: ministerios, hospitales y Carabineros con sede en una comuna no son compras de su municipalidad. Esas filas quedan en `filas_sin_comuna_rm`.
- **Filtro de montos extremos y fechas centinela:** valores mayores a `$10^{12}` CLP y fechas anteriores a `2000-01-01` se excluyen automáticamente.
- **Sin columna de reclamos:** `CantidadReclamos` se repite en cada licitación del comprador (un contador acumulado), así que sumarlo por licitación daba cifras imposibles (15 millones de reclamos en Santiago). No se puede verificar qué cuenta exactamente, por lo que se excluye.
- **Supuestos sin fuente en `core/licitaciones.py`:** `MIN_SAMPLE_ASSUMPTION = 20` licitaciones cerradas para usar la tasa como base y `MAX_EFFECTIVE_N_ASSUMPTION = 40` como tope del tamaño efectivo de la actualización Beta.
- **Advertencia de lectura:** una baja tasa de adjudicación o licitación con 1 oferente es una señal estadística operativa, **no** prueba de irregularidad por sí sola.
