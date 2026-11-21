# Mudanzas entre comunas, población y viviendas, Región Metropolitana (Censos 2017 y 2024)

Descarga realizada el 2026-11-21. Fuente: INE (Instituto Nacional de Estadísticas).
Licencia de los datos: CC BY-SA 4.0 (https://www.ine.gob.cl/terminos-de-uso-y-licencia-de-datos-abiertos).
Las tablas derivadas de este directorio heredan esa licencia y deben citar al INE. Se prohíbe
intentar reidentificar personas.

## Archivos

Códigos de comuna: CUT de cinco dígitos (13101 es Santiago). Son los mismos 52 códigos en ambos
censos.

| Archivo | Columnas | Contenido |
|---|---|---|
| `mudanzas_2012_2017.csv` | `codigo_origen`, `codigo_destino`, `personas` | Censo 2017. Origen: comuna donde la persona vivía hace 5 años (abril de 2012). Destino: comuna de residencia habitual al censo. 52 × 52 = 2.704 filas |
| `mudanzas_2019_2024.csv` | igual | Censo 2024. Origen: comuna donde vivía en abril de 2019. Destino: comuna de residencia habitual. 2.704 filas |
| `poblacion_viviendas.csv` | `codigo`, `comuna`, `anio`, `poblacion`, `viviendas` | Una fila por comuna y censo (104 filas) |

- **La diagonal** (origen = destino) cuenta a quienes vivían en la misma comuna en ambas fechas.
  Sirve para la inercia del modelo: la tasa de mudanza de una comuna es lo que sale de su fila
  dividido por el total de la fila.
- Un par sin mudanzas aparece con `personas = 0`. Ningún valor se interpoló ni se estimó.
- Solo entran personas con **las dos comunas conocidas y dentro de la RM**. Quedan fuera los
  menores de 5 años (aún no nacían), quienes vivían en el extranjero o en otra región, los que no
  respondieron y los que declararon la región pero no la comuna. Por eso la suma de una matriz
  es menor que la población.

| Control | 2012→2017 | 2019→2024 |
|---|---|---|
| Mudanzas entre comunas de la RM (fuera de la diagonal) | 910.411 | 993.528 |
| Permanecen en su comuna (diagonal) | 4.975.480 | 5.471.843 |
| Total en la matriz | 5.885.891 | 6.465.371 |
| Población de la RM en `poblacion_viviendas.csv` | 7.028.421 | 7.400.741 |
| Viviendas de la RM en `poblacion_viviendas.csv` | 2.378.442 | 2.764.749 |

Los totales de población y viviendas coinciden con las cifras oficiales del INE, y
`tests/test_censo.py` los comprueba.

## De dónde sale cada tabla

### 2019→2024: tabla ya publicada por el INE

- `D5_Migracion-interna.xlsx`, hoja `2`: «Población censada por comuna de residencia habitual hace
  5 años, según comuna de residencia habitual actual».
  https://censo2024.ine.gob.cl/wp-content/uploads/2025/04/D5_Migracion-interna.xlsx
- Filas: comuna actual. Columnas: comuna de hace 5 años, en el mismo orden que las filas. El script
  comprueba ese orden por nombre y se detiene si no calza.
- La celda de la diagonal viene como «-». Se reemplaza por la columna «No migrante interno
  comunal» de la misma fila.
- Pregunta del cuestionario 2024: «¿En qué comuna o país vivía en abril de 2019?»

### 2012→2017: construida desde los microdatos

No hay matriz comuna por comuna publicada. Se construye desde los microdatos de personas:
`Microdato_Censo2017-Personas.csv`, 2,6 GB, dentro de un RAR anidado aunque el archivo termine
en `.zip`.
https://www.ine.gob.cl/docs/default-source/censo-de-poblacion-y-vivienda/bbdd/censo-2017/csv/csv-personas-censo-2017.zip

Variables (manual de usuario Censo 2017, 16 regiones:
https://www.ine.gob.cl/docs/default-source/censo-de-poblacion-y-vivienda/bbdd/censo-2017/manual-de-usuario/manual_de_usuario_censo_2017_16r.pdf):

- `COMUNA`: comuna donde se censó a la persona.
- `P10`: residencia habitual. 1 en esta vivienda; 2 en otra vivienda; 3 en otra comuna
  (`P10COMUNA`); 4 en otro país.
- `P11`: residencia hace 5 años. 1 aún no nacía; 2 en esta comuna; 3 en otra comuna
  (`P11COMUNA`); 4 a 9 en otro país; 98 no aplica; 99 sin dato.
- `P11COMUNA`: 997 comuna no declarada; RR000 región conocida sin comuna (13000).

**El problema de 2017.** El Censo 2017 fue un censo **de hecho**: cuenta a cada persona donde
estaba ese día. El Censo 2024 fue **de derecho**: la cuenta donde vive. Para que ambas matrices
midan lo mismo:

- **Destino** = comuna de residencia habitual: `COMUNA` si `P10` es 1 o 2, `P10COMUNA` si `P10`
  es 3.
- **Origen**: `P11COMUNA` si `P11` es 3. Si `P11` es 2 («en esta comuna»), se usa `COMUNA`, pero
  solo cuando la persona vive donde se la censó.
- Se descartan **24.323 personas** de la RM que fueron censadas fuera de su comuna habitual y
  respondieron «en esta comuna». No se puede saber si esa respuesta se refiere a la comuna donde
  se censaron o a la suya.

Control: los residentes habituales de la RM con comuna conocida suman 7.028.421. Es exactamente
la suma de las 52 comunas en la tabla del INE.

### Población y viviendas

| Año | Población | Viviendas |
|---|---|---|
| 2024 | `D5_Migracion-interna.xlsx`, hoja `2`, «Población censada» (de derecho, equivale a residentes habituales) | `V1_Viviendas-y-hogares-censados.xlsx`, hoja `2`, «Viviendas censadas» (particulares ocupadas, desocupadas y colectivas). https://censo2024.ine.gob.cl/wp-content/uploads/2025/03/V1_Viviendas-y-hogares-censados.xlsx |
| 2017 | `Poblacion-censada-y-residentes-habituales-Censo-2017.xlsx`, hoja `2`, «Residentes habituales» (comparable con 2024). https://censo2024.ine.gob.cl/wp-content/uploads/2025/04/Poblacion-censada-y-residentes-habituales-Censo-2017.xlsx | Microdatos de viviendas, filas con `P01` entre 1 y 8 (excluye los operativos de tránsito y calle, que no son viviendas). Suma 2.378.442, igual al total que publica el INE para la RM (https://geoarchivos.ine.cl/File/pub/poblaci%C3%B3n-y-vivienda-metropolitana.pdf). https://www.ine.gob.cl/docs/default-source/censo-de-poblacion-y-vivienda/bbdd/censo-2017/csv/csv-viviendas-censo-2017.zip |

## Flujos externos: `flujos_externos.csv`

Las matrices de mudanzas solo cuentan movimientos entre comunas de la RM. Esta tabla agrega lo
que queda fuera, por comuna y período, para que el modelo de hogares deje de ser un sistema
cerrado.

| Columna | Qué cuenta (residentes de la comuna al censo, salvo `salen`) |
|---|---|
| `llegan_otras_regiones` | Hace 5 años vivían en otra región, ya sea con comuna conocida o con la comuna ignorada pero la región conocida |
| `salen_a_otras_regiones` | Hace 5 años vivían en esta comuna y hoy viven en otra región |
| `llegan_extranjero` | Hace 5 años vivían en otro país |
| `menores_5` | Aún no nacían. Son los nacidos en el período que sobreviven y viven en la comuna; **no son nacimientos** |
| `residencia_ignorada` | Sin comuna de origen utilizable: no respondieron, región ignorada, comuna de la RM ignorada y, solo en 2017, los casos ambiguos del censo de hecho |

| Total RM | 2012→2017 | 2019→2024 |
|---|---|---|
| Llegan desde otras regiones | 224.945 | 179.275 |
| Salen a otras regiones | 294.886 | 396.965 |
| Llegan desde el extranjero | 309.103 | 338.266 |
| Menores de 5 años | 459.039 | 348.546 |
| Residencia ignorada | 149.443 | 69.283 |

**La contabilidad cierra exacto.** Para cada comuna y cada período, la suma de su fila de la
matriz interna más las cuatro categorías de llegada da su población: 7.028.421 en 2017 y
7.400.741 en 2024. `tests/test_censo.py` lo comprueba comuna por comuna.

Origen de cada período:

- **2019→2024**: tabla D5, hoja `2`. Contiene las 346 comunas del país como origen, más las
  columnas «Comuna ignorada, Región de …», «fuera del país», «región ignorada» e «ignorada».
- **2012→2017**: microdatos, con las mismas reglas que la matriz interna. `P11` de 4 a 9
  significa otro país (Perú, Argentina, Bolivia, Ecuador, Colombia u otro). Un código RR000
  fuera de la RM cuenta como otra región.

Lo que el censo no puede medir:

- **Salidas al extranjero.** El censo solo cuenta a quienes viven en Chile.
- **Salidas de personas cuya comuna de origen en la RM es ignorada.** Están en otra región y no
  se pueden asignar a una comuna.
- **Nacimientos y defunciones.** `menores_5` mezcla nacimientos, mortalidad infantil y
  mudanzas de niños. Hay que sumar estadísticas vitales.


Al comparar períodos:

- Las salidas a otras regiones suben de 294.886 a 396.965 en un período que incluye la
  pandemia.
- `residencia_ignorada` es más alta en 2017 porque fue censo de hecho.

## Cómo reejecutar

```bash
uv pip install --python .venv/bin/python -e ".[dev,datos]"   # o: .venv/bin/pip install -e ".[dev,datos]"
.venv/bin/python -m datos.censo.fetch_censo
.venv/bin/python -m pytest tests/test_censo.py
```

Necesita `bsdtar` (incluido en macOS; en Linux viene en el paquete `libarchive-tools`). Los
crudos (~300 MB) se guardan en `data/raw/censo/`, que git ignora. El script no vuelve a
descargar lo que ya está ahí. El CSV de personas de 2017 se lee en streaming, sin escribir los
2,6 GB a disco.

Cada archivo crudo se compara con el SHA-256 de la descarga del 2026-11-21, registrado en
`FUENTES` dentro de `datos/censo/fetch_censo.py`. Si el INE vuelve a publicar un archivo, el
script se detiene en vez de procesarlo en silencio. Hay que revisar los totales de arriba antes
de actualizar el digest.

## Vacíos y advertencias conocidas

- **Comparabilidad.** 2017 fue de hecho y 2024 de derecho (ver arriba). Además, 2024 combinó
  entrevista con tablet, web y papel. Ambas preguntas miden 5 años. No verifiqué el texto exacto
  de la pregunta P11 en el cuestionario 2017; el informe INE de migración interna indica abril
  de 2012 como referencia.
- **Omisión censal.** Las matrices no corrigen la omisión. Un medio informó ~7 % de omisión en
  2024 frente a 4,7 % en 2017. **No está verificado en una fuente del INE.**
- **No respuesta en 2017**: P11 2,56 %, P11COMUNA 2,31 % (manual 2017, anexo). Esos casos quedan
  fuera; no se prorratean.
- **Anonimización 2024.** El INE suprime la comuna de hace 5 años en comunas de menos de 6.000
  personas. No afecta a la RM: la comuna más chica es Alhué, con 7.768.
- **Años atípicos.** El período 2019→2024 incluye el estallido de 2019 y la pandemia. Si las
  mudanzas de ese período difieren de las de 2012→2017, parte de la diferencia puede venir de ahí
  y no del aire ni de la seguridad.
- **Solo mudanzas dentro de la RM.** Las llegadas desde otras regiones o desde el extranjero
  quedan fuera de las matrices. El modelo no las tiene como flujo entre comunas.
