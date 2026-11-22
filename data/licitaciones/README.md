# Licitaciones públicas de Mercado Público (ChileCompra), Región Metropolitana

Ingesta reproducible de licitaciones mensuales publicadas en los **Datos Abiertos de ChileCompra** para las 52 comunas de la Región Metropolitana (`data/comunas_rm.csv`).

> **Estado actual en el repo:** descargado y procesado el **2026-11-21** para todo el año **2024 (`2024-01` a `2024-12`)**: 12 archivos ZIP (~270 MB) versionados con **Git LFS** en `data/raw/licitaciones/` (`2024-1.zip` … `2024-12.zip`), que produjeron `236.576` líneas de compras municipales de la RM (sobre `2.512.286` filas totales), **52/52 comunas** en `resumen_comuna_anio.csv`, `292` filas en `resumen_sector_comuna.csv`, `16.068` licitaciones en `licitaciones_detalle.csv` y `5` montos extremos filtrados (`manifest.json`).

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
| `adjudicadas` | Licitaciones en estado adjudicado (`CodigoEstado` `8` o `9`, o texto `Adjudicada`) |
| `fallidas` | Licitaciones desiertas, revocadas o suspendidas (`CodigoEstado` `7`, `15`, `16`) |
| `cerradas` | `adjudicadas + fallidas` (denominador de la tasa de adjudicación) |
| `tasa_adjudicacion` | `adjudicadas / cerradas` (vacío si `cerradas = 0`) |
| `mediana_dias_pub_cierre` | Mediana de días entre publicación y cierre |
| `mediana_dias_pub_adj` | Mediana de días entre publicación y adjudicación |
| `mediana_oferentes` | Mediana de oferentes participantes |
| `proporcion_oferente_unico` | Fracción de licitaciones con exactamente 1 oferente |
| `monto_estimado_clp` | Suma deduplicada de `MontoEstimado` en pesos (sin otras monedas ni errores extremos > $1 billón) |
| `monto_adjudicado_clp` | Suma de `MontoLineaAdjudica` por línea en pesos (sin otras monedas ni outliers > $1 billón). Es un piso, no el gasto total: ver límites |

### `licitaciones_detalle.csv`

Una fila por licitación deduplicada `(codigo_comuna, codigo_externo)`, escrita desde las mismas licitaciones que cuentan los resúmenes: por comuna y año, sus conteos de `estado` coinciden exactamente con `total_licitaciones`, `adjudicadas`, `fallidas` y `cerradas` de `resumen_comuna_anio.csv`.

| Columna | Descripción |
|---|---|
| `codigo_comuna`, `anio`, `codigo_externo` | Comuna (CUT), año de publicación y código de la licitación |
| `nombre` | Nombre de la licitación (`Nombre`, primer valor no vacío entre sus líneas) |
| `estado` | `adjudicada`, `fallida` o `abierta` (ni adjudicada ni fallida, incluye «Cerrada» sin resolver). Si una línea la reporta adjudicada y otra fallida, gana adjudicada, igual que en los resúmenes |
| `estado_chilecompra` | Etiqueta original de ChileCompra (`Estado` normalizado, o el código si falta) |
| `sector` | Mismo clasificador por palabras clave que `resumen_sector_comuna.csv` |
| `monto_estimado_clp` | `MontoEstimado` en pesos (vacío si falta o está en otra moneda) |
| `monto_adjudicado_clp` | Suma de `MontoLineaAdjudica` en pesos; vacío si ninguna línea trae monto. Es un piso (ver límites) |
| `numero_oferentes`, `dias_pub_cierre`, `dias_pub_adj` | Máximo de oferentes y días entre publicación y cierre / adjudicación |

### `viz/datos/licitaciones.json` (aporte por licitación)

`make licitaciones-detalle` (`experiments/licitaciones_aporte.py`) lee `licitaciones_detalle.csv` y `viz/datos/simulacion.json` y escribe, por comuna, sus conteos, la credibilidad municipal y sus licitaciones con `aporte_credibilidad`: el cambio exacto de la media posterior al quitar esa licitación (`media_con - media_sin`), con el mismo prior (`SECURITY_CREDIBILITY`), año (`PROCUREMENT_YEAR`) y `estimate_commune_credibility` que la simulación. Solo las comunas de `politicas[].credibilidad_por_comuna` tienen `afecta_modelo: true`; en las demás, y en las licitaciones abiertas, el aporte es 0 porque no entran al modelo. El script falla sin escribir si los conteos del detalle no coinciden con `resumen_comuna_anio.csv` o si la media recalculada no coincide con `credibilidad_por_comuna.media`. Con más de 40 cerradas el tamaño efectivo queda fijo, así que los aportes no son aditivos (adjudicadas × aporte + fallidas × aporte ≈ 0), y el efecto de una licitación sobre los delitos simulados queda bajo la resolución Monte Carlo: no se publica.

### `resumen_sector_comuna.csv`

Una fila por `(codigo_comuna, sector)` clasificada por palabras clave determinísticas en título, descripción y producto (`agua`, `energia`, `aire_calefaccion`, `seguridad`, `infraestructura`, `otros`).

### `manifest.json`

Metadatos de trazabilidad: URLs, hashes SHA-256 y conteos diagnósticos (`total_filas`, `filas_rm`, `filas_sin_comuna_rm`, `outliers_monto_filtrados`, `filas_moneda_no_clp`).

## Reglas y límites conocidos

- **Deduplicación por `CodigoExterno`:** los estados, fechas, oferentes y `MontoEstimado` se toman una sola vez por licitación; solo `MontoLineaAdjudica` se suma entre ítems.
- **Solo compras municipales:** se asigna `codigo_comuna` solo si `NombreOrganismo` es `Municipalidad de <comuna>` (con variantes «I. Municipalidad», «Ilustre Municipalidad» y la normalización `"Til Til"` → `"Tiltil"`, `13303`). La ubicación de la unidad compradora (`ComunaUnidad`) se ignora a propósito: ministerios, hospitales y Carabineros con sede en una comuna no son compras de su municipalidad. Esas filas quedan en `filas_sin_comuna_rm`.
- **Estados por código:** en los ZIP de 2024, `CodigoEstado` 8 y 9 son «Adjudicada», 7 «Desierta», 15 «Revocada» y 16 «Suspendida»; 6 y 11 a 14 son «Cerrada» (sin resolver) y no cuentan como cerradas para la tasa.
- **Solo pesos:** las líneas en UF, dólares, euros o «Moneda revisar» siguen contando como licitaciones, pero su monto no se suma (`filas_moneda_no_clp`: 938 líneas). Sumarlas como pesos inflaba el monto estimado en unos $37.500 millones.
- **`monto_adjudicado_clp` es un piso:** algunas líneas se adjudican como porcentaje o tarifa unitaria (un precio unitario de 0,64 frente a un monto estimado de $371 millones), así que la suma por línea subestima el gasto. En la mediana de las comunas, lo adjudicado es el 41 % de lo estimado. Úsalo para comparar comunas entre sí, no como gasto municipal total.
- **Filtro de montos extremos y fechas centinela:** valores mayores a `$10^{12}` CLP y fechas anteriores a `2000-01-01` se excluyen automáticamente.
- **Sin columna de reclamos:** `CantidadReclamos` se repite en cada licitación del comprador (un contador acumulado), así que sumarlo por licitación daba cifras imposibles (15 millones de reclamos en Santiago). No se puede verificar qué cuenta exactamente, por lo que se excluye.
- **Supuestos sin fuente en `core/licitaciones.py`:** `MIN_SAMPLE_ASSUMPTION = 20` licitaciones cerradas para usar la tasa como base y `MAX_EFFECTIVE_N_ASSUMPTION = 40` como tope del tamaño efectivo de la actualización Beta.
- **Advertencia de lectura:** una baja tasa de adjudicación o licitación con 1 oferente es una señal estadística operativa, **no** prueba de irregularidad por sí sola.
