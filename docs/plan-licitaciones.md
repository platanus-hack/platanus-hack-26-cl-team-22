# Plan de ingesta de licitaciones públicas (ChileCompra)

Los datos de licitaciones de Mercado Público ingresan al simulador mediante la descarga masiva de ZIPs mensuales oficiales de **Datos Abiertos de ChileCompra** (`https://transparenciachc.blob.core.windows.net/lic-da/{year}-{month}.zip`), deduplicando líneas de ítem por `CodigoExterno` y cruzando las 52 comunas de la Región Metropolitana (`data/comunas_rm.csv`) para alimentar la credibilidad de ejecución en `core/licitaciones.py`.

> **Estado actual:** descargado el **2026-11-21** para el período **2024-01 a 2024-12** (`12` ZIPs / ~270 MB en `data/raw/licitaciones/*.zip` versionados con **Git LFS**). `manifest.json` registra `2.512.286` filas totales, `681.828` líneas RM, `5` montos extremos filtrados, **52/52 comunas** en `resumen_comuna_anio.csv` y `307` cruces en `resumen_sector_comuna.csv`. `experiments/simular.py` reporta `meta.licitaciones.disponible = true` con `comunas_con_datos = 52`.

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
               ├─ empareja ComunaUnidad / Municipalidad -> CUT 5 dígitos
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
| `datos/licitaciones/enriquecer_ficha.py` | Consulta puntual de fichas individuales vía `https://api.licitalab.cl/free/tender/{id}` | Tope de 9 req/min y caché en `data/raw/licitaciones/fichas/`; opt-in, nunca masivo |
| `core/licitaciones.py` | Actualiza un prior `BetaCredibility` usando `adjudicadas` vs `cerradas` por comuna | `max_effective_n = 40` evita bandas artificialmente angostas |

## Reglas de diseño y tradeoffs

| Decisión | Alternativa descartada | Por qué se eligió |
|---|---|---|
| **ZIPs oficiales de ChileCompra** (`transparenciachc`) | Scrapers ASP.NET (`__VIEWSTATE`) o `api.licitalab.cl` masivo | Los dumps oficiales entregan años completos en minutos con SHA-256 auditable; los scrapers tienen rate limit de 9 req/min y dependen del DOM |
| **Deduplicación por `(codigo_comuna, codigo_externo)`** | Contar cada fila del CSV como licitación | En ChileCompra cada línea de ítem repite `CodigoExterno`, estado, fechas y `MontoEstimado`; solo `MontoLineaAdjudica` debe sumarse entre líneas |
| **Emparejamiento conservador de comunas** | Asignar organismos nacionales o ministerios a Santiago (`13101`) | Solo se asigna CUT si `ComunaUnidad` calza con una de las 52 comunas RM o si `NombreOrganismo` es `Municipalidad de <comuna>`; los casos ambiguos quedan fuera y se reportan en `filas_sin_comuna_rm` |
| **Tope de tamaño efectivo (`max_effective_n = 40`)** | Actualizar la Beta con cientos de licitaciones crudas sin escala | Mantiene la media empírica (`adjudicadas / cerradas`) sin colapsar la banda p10–p90 a cero frente a otros factores de ejecución |

## Cómo se conecta con `core/credibilidad.py`

`estimate_commune_credibility()` devuelve un `ProcurementCredibilityEstimate` compatible con `BetaCredibility` y `Provenance`:

- **`cerradas == 0` o sin CSV:** conserva el prior (`provenance = "supuesto"`).
- **`0 < cerradas < min_sample` (20):** actualiza el prior con muestra reducida (`provenance = "tasa_base"`).
- **`cerradas >= min_sample`:** marca la credibilidad comunal como observada (`provenance = "medida"`).

> [!NOTE]
> La tasa de adjudicación de ChileCompra mide capacidad operativa para cerrar licitaciones, no el cumplimiento físico de metas ambientales. Úsala como tasa base municipal o covariable de riesgo operativo, declarando siempre su procedencia en `simulacion.json`.

## Checklist de verificación

- [x] `make licitaciones` descargó los 12 ZIPs de 2024 en `data/raw/licitaciones/` (versionados con Git LFS) y generó `resumen_comuna_anio.csv`, `resumen_sector_comuna.csv` y `manifest.json`.
- [x] `manifest.json` registra `outliers_monto_filtrados` (5), `filas_sin_comuna_rm` (1.830.458) y SHA-256 por archivo.
- [x] `make simulate` reporta `meta.licitaciones.disponible: true` y `comunas_con_datos: 52` en `viz/datos/simulacion.json`.
- [x] `make lint && make test` termina en verde sin modificar el esquema existente de `simulacion.json`.

## Siguiente paso

Revisar [`data/licitaciones/README.md`](../data/licitaciones/README.md) para el detalle columna por columna y el alcance de `CantidadReclamos`. Si necesitás reprocesar sin red a partir de los ZIPs ya versionados por LFS, ejecutá `.venv/bin/python -m datos.licitaciones.fetch_licitaciones --desde 2024-01 --hasta 2024-12 --solo-locales`.
