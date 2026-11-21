# Permisos de edificación de vivienda por comuna, Región Metropolitana, 2002–2024

Descarga realizada el 2026-11-21.

Fuente: MINVU, Centro de Estudios de Ciudad y Territorio, «Viviendas unidades y superficie según
año y comuna 2002 a sep 2026». Se construye con el Formulario Único de Estadística de Edificación
del INE e incluye obra nueva y regularización de obra nueva.
https://catalogo.minvu.cl/cgi-bin/koha/opac-retrieve-file.pl?id=d40a41546b26b2a7fe5f1440af6e6ff2

La página no declara licencia: se cita la fuente. Antes de redistribuir fuera del proyecto, hay
que confirmar los términos con el MINVU.

## Archivo

`permisos_vivienda.csv` tiene las columnas `codigo`, `comuna`, `anio`, `viviendas`,
`departamentos`, `casas` y `m2`. Son 52 comunas × 23 años (2002–2024): 1.196 filas.

- `viviendas`: unidades de vivienda aprobadas en el año, igual a `departamentos` + `casas`.
- `m2`: superficie aprobada.
- Solo entran años definitivos. La tabla dice: «Los datos registrados hasta el año 2024 son
  definitivos». 2025 es preliminar y 2026 está incompleto.

## Controles

- En cada hoja y cada año, las 52 comunas suman exactamente la fila «Metropolitana». El script
  lee el valor guardado de esa fórmula y se detiene si no cuadra.
- `tests/test_vivienda.py` fija los totales de la RM: 39.027 en 2012, 49.082 en 2017 y 71.262
  en 2021.
- **Los permisos anticipan las viviendas nuevas.** Los permisos 2015–2020 tienen correlación
  **0,925** por comuna con el aumento de viviendas entre los censos 2017 y 2024. En volumen,
  suman 365.242 contra 386.307 viviendas nuevas. El rezago entre permiso y vivienda habitada
  ronda los 2 años.

## Advertencias

- **Un permiso no es una vivienda construida.** No encontré una serie pública de recepciones
  finales por comuna, y las recepciones georreferenciadas del INE requieren un token.
- **Ñuñoa:** 49.445 permisos entre 2016 y 2021, pero el censo solo suma 29.271 viviendas nuevas
  entre 2017 y 2024. Después los permisos se desploman: 14.528 en 2021, 1.740 en 2022 y 58 en
  2023. Es compatible con un adelanto de permisos antes de un cambio normativo, con muchos sin
  construir todavía. **La causa no está verificada.**
- La serie incluye «regularización obra nueva», no solo obra nueva.
- Las comunas vienen por nombre. Se cruzan con `data/censo/poblacion_viviendas.csv` sin
  distinguir tildes, mayúsculas ni espacios.

## Cómo reejecutar

```bash
.venv/bin/python -m datos.vivienda.fetch_permisos
```

El archivo crudo se guarda en `data/raw/vivienda/`, que git ignora, y se compara con su
SHA-256.
