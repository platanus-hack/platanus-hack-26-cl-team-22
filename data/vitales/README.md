# Nacimientos y defunciones por comuna, Región Metropolitana, 2012–2023

Descarga realizada el 2026-11-21. Fuente: INE, Anuarios de Estadísticas Vitales, cuadro
1.2.2-04, «Nacidos vivos, … defunciones: generales … según región, provincia y comuna de
residencia».
Licencia: CC BY-SA 4.0 (https://www.ine.gob.cl/terminos-de-uso-y-licencia-de-datos-abiertos).

## Archivo

`nacimientos_defunciones.csv` tiene las columnas `codigo`, `comuna`, `anio`, `nacimientos` y
`defunciones`. Son 52 comunas × 12 años = 624 filas, y el código es el CUT de cinco dígitos.

- **Nacimientos**: nacidos vivos según la comuna de residencia de la madre.
- **Defunciones**: defunciones generales según la comuna de residencia del fallecido.

Totales de la RM:

| Año | Nacimientos | Defunciones |
|---|---|---|
| 2012 | 99.488 | 37.286 |
| 2013 | 99.081 | 37.565 |
| 2014 | 103.059 | 38.840 |
| 2015 | 101.087 | 39.080 |
| 2016 | 96.616 | 39.281 |
| 2017 | 92.727 | 40.383 |
| 2018 | 95.834 | 39.953 |
| 2019 | 89.770 | 41.866 |
| 2020 | 81.351 | 51.600 |
| 2021 | 73.062 | 51.532 |
| 2022 | 76.129 | 49.967 |
| 2023 | 68.866 | 44.634 |

## Controles

- **Dentro de cada anuario**: el script exige que las 52 comunas sumen exactamente la fila
  «METROPOLITANA» del mismo cuadro, en nacimientos y en defunciones. Si no suman, se detiene.
- **Contra los microdatos del DEIS (MINSAL)**:
  - Los nacimientos coinciden exacto con la serie regional en 10 de los 12 años; difieren en 1
    en 2016 y en 2019.
  - Las defunciones difieren en 1 a 4 casos en 2014, 2015, 2016 y 2017, y coinciden en los
    demás años.
  - Son revisiones entre fuentes. `tests/test_vitales.py` fija los totales de 2012, 2017 y
    2023.

## Por qué el anuario y no el DEIS

Los microdatos abiertos de nacimientos del DEIS solo traen la región de residencia de la madre
(`REGION_RESIDENCIA`), no la comuna. El anuario del INE es la fuente oficial publicada que trae
nacimientos y defunciones por comuna en el mismo cuadro.

## Cómo se lee cada anuario

- El cuadro identifica a las comunas **por nombre**, sin código. El nombre se cruza con
  `data/censo/poblacion_viviendas.csv` sin distinguir tildes, mayúsculas ni espacios, así que
  «Tiltil» y «Til Til» son la misma comuna.
- Santiago, Talagante y Melipilla aparecen primero como provincia y después como comuna. Se usa
  la última fila con ese nombre.
- Cambios de formato entre años:
  - **Hasta 2020** hay una columna por concepto. En 2015, 2019 y 2020, «Generales» está una fila
    más abajo que «Nacidos vivos».
  - **Desde 2021** nacimientos y defunciones vienen por sexo (hombre, mujer e indeterminado) y
    se suman.
  - **2016**: el cuadro está en el archivo de nacimientos de ese año.

## Cómo reejecutar

```bash
.venv/bin/python -m datos.vitales.fetch_vitales
```

Necesita antes `data/censo/poblacion_viviendas.csv`. Los anuarios se guardan en
`data/raw/vitales/`, que git ignora, y cada uno se compara con su SHA-256.

## Vacíos y advertencias

- **Sin 2024 por comuna.** El INE solo publicó cifras provisionales de 2024 por región y
  todavía no hay anuario. Para el período del censo 2019→2024 hay datos de 2019 a 2023.
- **2020 y 2021 tienen exceso de defunciones por COVID**: 51.600 y 51.532, frente a 41.866 en
  2019. Para estimar una tasa de mortalidad que se proyecte a 2036, conviene excluir esos años
  o tratarlos aparte.
- **Los nacimientos caen fuerte**: de 99.488 en 2012 a 68.866 en 2023 (−31 %). Una tasa promedio
  de 2012 a 2017 sobreestima los nacimientos actuales; la tendencia importa.
- **Inscripción tardía**: los años recientes pueden subir un poco cuando el INE los revise.
- La nacionalidad de la madre no se usa aquí. Además, en las fuentes viene mal codificada antes
  de 2016.
