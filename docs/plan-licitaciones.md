# Plan de ingesta de licitaciones públicas (ChileCompra)

Los datos de licitaciones de Mercado Público ingresan al simulador mediante la descarga masiva de ZIPs mensuales oficiales de **Datos Abiertos de ChileCompra** (`https://transparenciachc.blob.core.windows.net/lic-da/{year}-{month}.zip`), deduplicando líneas de ítem por `CodigoExterno` y cruzando las 52 comunas de la Región Metropolitana (`data/comunas_rm.csv`) para alimentar la credibilidad de ejecución en `core/licitaciones.py`.

> **Estado actual:** descargado el **2026-11-21** para el período **2024-01 a 2024-12** (`12` ZIPs / ~270 MB en `data/raw/licitaciones/*.zip` versionados con **Git LFS**). `manifest.json` registra `2.512.286` filas totales, `236.576` líneas de compras municipales de la RM, `5` montos extremos filtrados, **52/52 comunas** en `resumen_comuna_anio.csv` y `292` cruces en `resumen_sector_comuna.csv`. Ninguna salida del modelo usa todavía estos datos: `core/licitaciones.py` es una biblioteca con tests.

## Ruta rápida

1. Ejecutar la descarga y agregación para el año de corte (requiere salida a red):

   ```bash
   make licitaciones
   # equivalente con rango explícito:
   .venv/bin/python -m datos.licitaciones.fetch_licitaciones --desde 2024-01 --hasta 2024-12
   ```

2. Regenerar la simulación con el indicador actualizado en `simulacion.json`:

   ```bash
   make simulate
   ```

3. Verificar pruebas y lint antes de abrir PR:

   ```bash
   make lint && make test
   ```

## Arquitectura y flujo de datos

```text
transparenciachc.blob.core.windows.net/lic-da/{year}-{month}.zip
   └─> data/raw/licitaciones/*.zip      (caché local versionado con Git LFS)
         └─> datos/licitaciones/esquema.py
               ├─ deduplica CodigoExterno (mantiene suma de MontoLineaAdjudica)
               ├─ empareja solo «Municipalidad de <comuna>» -> CUT 5 dígitos
               └─ clasifica sector (agua, energia, aire_calefaccion, seguridad, infraestructura, otros)
         └─> data/licitaciones/
               ├─ resumen_comuna_anio.csv
               ├─ resumen_sector_comuna.csv
               └─ manifest.json        (URLs, fecha, SHA-256 y diagnósticos)
         └─> core/licitaciones.py      (Beta-Binomial con tope de muestra efectiva)
```

| Componente | Responsabilidad | Restricción clave |
|---|---|---|
| `datos/licitaciones/fetch_licitaciones.py` | Descarga ZIPs mensuales, verifica cabecera `PK\x03\x04` y genera CSVs + `manifest.json` | Soporta `--solo-locales` para reprocesar sin red |
| `datos/licitaciones/esquema.py` | Normaliza números chilenos (`1.234,56`), fechas, montos extremos y deduplicación por `CodigoExterno` | Filtra montos `> $10^{12}` CLP y fechas `< 2000-01-01` |
| `core/licitaciones.py` | Actualiza un prior `BetaCredibility` usando `adjudicadas` vs `cerradas` por comuna | `MAX_EFFECTIVE_N_ASSUMPTION = 40` (supuesto, sin fuente) evita bandas artificialmente angostas |

## Reglas de diseño y tradeoffs

| Decisión | Alternativa descartada | Por qué se eligió |
|---|---|---|
| **ZIPs oficiales de ChileCompra** (`transparenciachc`) | Scrapers ASP.NET (`__VIEWSTATE`) o `api.licitalab.cl` masivo | Los dumps oficiales entregan años completos en minutos con SHA-256 auditable; los scrapers tienen rate limit de 9 req/min y dependen del DOM |
| **Deduplicación por `(codigo_comuna, codigo_externo)`** | Contar cada fila del CSV como licitación | En ChileCompra cada línea de ítem repite `CodigoExterno`, estado, fechas y `MontoEstimado`; solo `MontoLineaAdjudica` debe sumarse entre líneas |
| **Solo compras municipales** | Asignar a una comuna todo comprador ubicado en ella (`ComunaUnidad`) | Solo se asigna CUT si `NombreOrganismo` es `Municipalidad de <comuna>`. Ministerios, hospitales, Carabineros y corporaciones con sede en una comuna no son compras de su municipalidad y quedan en `filas_sin_comuna_rm` |
| **Tope de tamaño efectivo (`MAX_EFFECTIVE_N_ASSUMPTION = 40`, supuesto sin fuente)** | Actualizar la Beta con cientos de licitaciones crudas sin escala | Evita que la banda p10–p90 colapse a cero. La media posterior queda entre el prior y la tasa observada; no es igual a la tasa |

## Cómo se conecta con `core/credibilidad.py`

`estimate_commune_credibility()` devuelve un `ProcurementCredibilityEstimate` compatible con `BetaCredibility` y `Provenance`:

- **`cerradas == 0` o sin CSV:** conserva el prior (`provenance = "supuesto"`).
- **`cerradas < MIN_SAMPLE_ASSUMPTION` (20, supuesto sin fuente):** actualiza el prior pero la procedencia sigue siendo `"supuesto"`.
- **`cerradas >= MIN_SAMPLE_ASSUMPTION`:** la tasa de adjudicación queda como tasa base municipal (`"tasa_base"`). Nunca `"medida"`: adjudicar una licitación no es ejecutar una medida.

> [!NOTE]
> La tasa de adjudicación de ChileCompra mide capacidad operativa para cerrar licitaciones, no el cumplimiento físico de metas ambientales. Úsala como tasa base municipal o covariable de riesgo operativo, declarando siempre su procedencia en `simulacion.json`.

## Checklist de verificación

- [x] `make licitaciones` descargó los 12 ZIPs de 2024 en `data/raw/licitaciones/` (versionados con Git LFS) y generó `resumen_comuna_anio.csv`, `resumen_sector_comuna.csv` y `manifest.json`.
- [x] `manifest.json` registra `outliers_monto_filtrados` (5), `filas_sin_comuna_rm` (1.830.458) y SHA-256 por archivo.
- [x] `make simulate` reporta `meta.licitaciones.disponible: true` y `comunas_con_datos: 52` en `viz/datos/simulacion.json`.
- [x] `make lint && make test` termina en verde sin modificar el esquema existente de `simulacion.json`.

## Siguiente paso

Revisar [`data/licitaciones/README.md`](../data/licitaciones/README.md) para el detalle columna por columna. Si necesitás reprocesar sin red a partir de los ZIPs ya versionados por LFS, ejecutá `.venv/bin/python -m datos.licitaciones.fetch_licitaciones --desde 2024-01 --hasta 2024-12 --solo-locales`.
