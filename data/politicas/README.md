# Cumplimiento del PPDA RM — fuente y límites

Tabla de conformidad de las medidas del Plan de Prevención y Descontaminación
Atmosférica de la Región Metropolitana (PPDA RM, D.S. 31/2016), a partir del
informe de revisión encargado por la SEREMI del Medio Ambiente RM.

## Fuente

- Documento: *Informe Final — Revisión de las medidas del PPDA Región
  Metropolitana*, ECOS-Chile, licitación ID 608897-78-LE23 / PROY-536-SSA-2023.
  Corte de información: 24 de noviembre de 2023.
- URL: <https://airerm.mma.gob.cl/wp-content/uploads/2024/03/2023_Informe-Revision-PPDA.pdf>
- Copia local: `data/raw/politicas/2023_Informe-Revision-PPDA.pdf` (3.588.823 bytes)
- `sha256`: `4a4446d21b58d026267a7d8274e2af641a7e8c96d5a5337eef99292847ed69fa`
- Fecha de descarga: **2026-11-21**

## Lo primero: no existe tabla medida por medida

El PDF **no trae la tabla de 157 medidas una por una**. Lo que publica son
conteos agregados por capítulo y un ejemplo de ficha. Evidencia:

| Página del PDF | Qué dice |
|---|---|
| 67 | Tabla 18: 38 conformes, 33 parcialmente conformes, 86 no conformes = 157 |
| 121 | "estas fichas de revisión se encuentran anexadas al presenten informe" (sic), pero solo se muestran figuras de ejemplo |
| 123 | Una única ficha completa de ejemplo (código FER-05, "No conforme") |
| 159 | Las fichas por capítulo y la planilla de sistematización están en documentos aparte del repositorio digital: "Fichas de revisión separadas por capítulos (set de documentos en pdf)" y "Matriz de Sistematización PPDA 2023" |

Prueba cuantitativa: en 159 páginas aparecen **6 códigos de medida** en total
(CBB-01, CMP-04, DEF-01, EAP-03, FER-05, GEN-02). Una tabla de 157 medidas
nombraría alrededor de 157.

Por eso **no se creó `medidas_ppda.csv`**: llenarlo con 157 filas habría exigido
inventar medidas, estados y artículos. Lo que sí está respaldado es el nivel de
capítulo.

## Qué se entrega

`data/politicas/cumplimiento_ppda_capitulos.csv` — 10 filas, una por capítulo
del PPDA evaluado (III a XII):

| Columna | Contenido |
|---|---|
| `capitulo` | Capítulo del D.S. 31 (III a XII) |
| `tema` | Título del capítulo según el informe |
| `fuente_objetivo` | `lena` \| `transporte` \| `industria` \| `quemas` \| `episodios` \| `otra` |
| `medidas_unicas_declaradas` | Códigos únicos del capítulo, solo si el informe los declara (vacío si no) |
| `medidas_evaluadas` | Base de los conteos: una medida por organismo responsable |
| `conformes`, `parciales`, `no_conformes` | Conteos del informe |
| `tasa_conforme`, `tasa_conforme_o_parcial` | Derivadas (conformes / evaluadas) |
| `pagina_pdf` | Página(s) del PDF con la evidencia |
| `cita` | Frases literales que respaldan los conteos |

Mapeo a `fuente_objetivo` por capítulo: III → `transporte`, VI → `industria`,
VII → `lena`, VIII → `quemas`, X → `transporte`, XII → `episodios`. Los capítulos
IV (combustibles), V (COV de distribución de combustibles), IX (polvo y áreas
verdes) y XI (educación ambiental) quedan en `otra` porque no calzan con una
sola fuente.

## Cómo se extrajo

`datos/politicas/build_credibilidad.py`:

1. Descarga el PDF al caché (`data/raw/politicas/`) si falta o si el `sha256`
   no calza. No ejecuta nada del archivo descargado.
2. Extrae el texto con `pypdf` (el PDF tiene capa de texto; no es un escaneo).
3. Verifica que la Tabla 18 diga `38 33 86 157` y que **cada** cifra y cita
   usada exista literalmente en la página citada. Si un fragmento no aparece,
   el script falla y no escribe el CSV.
4. Escribe el CSV y reporta el diagnóstico.

```bash
C:/Users/gabod/Proyectos/platanus-hack-26-cl-team-22/.venv/Scripts/python -I datos/politicas/build_credibilidad.py
```

Las citas son literales con espacios normalizados (los saltos de línea del PDF
se colapsan a un espacio) y las frases separadas por `...` vienen de oraciones
distintas del mismo bloque.

## Conteos: lo que calza y lo que no

- **Global (Tabla 18, p. 67): 157 medidas → 38 conformes (24 %), 33 parciales
  (21 %), 86 no conformes (55 %).** Coincide con el resumen del informe.
- **Suma de las filas por capítulo: 186 medidas → 42 conformes, 48 parciales,
  96 no conformes.** No calza con 157, y es esperable: la Tabla 18 cuenta
  códigos únicos y, según su nota 11, excluye los registros "No aplica";
  los capítulos cuentan cada medida una vez por organismo responsable (el propio
  informe lo dice en el acápite 7.1 y lo ejemplifica con CMP-04 y EAP-03).
- Consecuencia práctica: **las tasas por capítulo son más confiables que
  cualquier intento de reconciliar 157 filas.**

## Advertencias de lectura

- **"No conforme" ≠ incumplimiento.** En esta revisión significa que no hubo
  evidencia pública suficiente para corroborar la medida en 2018-2022
  (pp. 67, 74, 110). No es una medición de incumplimiento demostrado.
- Los conteos por capítulo son de la base "una medida por organismo". Para
  usarlos como credibilidad de ejecución conviene tomar
  `tasa_conforme_o_parcial` como cota superior y `tasa_conforme` como cota
  inferior.
- Capítulo IV (combustibles): el informe declara 11 medidas únicas pero evalúa
  12 (11 SEC + 1 MMA), todas no conformes.

## Vacíos y dudas

- **No hay detalle por medida.** Las fichas por medida y la planilla Excel no
  están publicadas con el informe. Sin esos documentos no se puede bajar de
  capítulo a medida.
- **El informe de avance SMA 2024 tampoco lo tiene**: su detalle por medida está
  en un "Anexo digital, planilla Excel" que el PDF menciona (p. 16) pero no
  incluye. Además usa otro universo: 162 medidas (105 permanentes, 57 no
  permanentes), taxonomía distinta a las 157 de ECOS.
- **`articulo` y `tipo` (permanente / no permanente) no se pudieron llenar**:
  el informe de ECOS no asigna artículos del D.S. 31 a las medidas por capítulo,
  y la clasificación permanente / no permanente es de la SMA, no de esta
  revisión.
- El PDF no declara artículos por medida en ningún pasaje; los artículos que
  aparecen (por ejemplo el 66 en la ficha de ejemplo) son ilustrativos.
- Fecha de descarga registrada según lo pedido: 2026-11-21. El PDF no incluye
  fecha de publicación en el sitio; su metadato interno es 2023-12-27.

## Archivos

- `data/raw/politicas/2023_Informe-Revision-PPDA.pdf` — PDF tal como se descargó
- `datos/politicas/build_credibilidad.py` — descarga con caché + extracción + verificación
- `data/politicas/cumplimiento_ppda_capitulos.csv` — tabla por capítulo
- `data/politicas/README.md` — este archivo
