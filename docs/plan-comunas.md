# Plan de construcción: Simulador de comunas

Estado al 21 de noviembre de 2026. Este plan reparte el trabajo en frentes que avanzan
en paralelo. Complementa `work-plan.md` (roles y horas) y las observaciones al whitepaper.
El contexto base del proyecto (decisiones, modelo, datos, validación, demo) está en
[`contexto-proyecto.md`](./contexto-proyecto.md).

## La decisión de arquitectura

El modelo corre en Python, antes de la demo, y escribe un archivo JSON. La interfaz es
una página estática que solo lee ese archivo.

- **Sin servidor en la demo**: no hay nada que se pueda caer en el escenario.
- **Interfaz y modelo no se bloquean**: el contrato de abajo es lo único que comparten.
- **Límite**: la interfaz solo puede mostrar escenarios ya calculados. Por eso se calcula
  el escenario base y uno por cada política apagada.

```
datos/ (descarga)  ->  data/ (tablas limpias)  ->  core/ (modelo)  ->  experiments/ (réplicas)
                                                                             |
                                                              viz/datos/simulacion.json
                                                                             |
                                                                  viz/ (página estática)
```

## El contrato: `simulacion.json`

Hay un archivo de ejemplo en `viz/ejemplo/simulacion.json`. Se regenera con
`python -m experiments.ejemplo_viz`. Solo la línea base es real; lo demás es inventado
con semilla fija para que la interfaz tenga la forma correcta.

| Clave | Contenido |
|---|---|
| `meta` | Versión, semilla, año base, lista de años y `es_ejemplo` |
| `variables` | Cada variable proyectada: id, nombre, unidad y si menor es mejor |
| `comunas` | Código, nombre, latitud, longitud y valor base por variable |
| `tipos_hogar` | Perfiles de partida con sus pesos por variable |
| `politicas` | Id, nombre, nivel (regional, comunal o proyecto), fuente, comunas y credibilidad (p10, media, p90) |
| `escenarios` | Id, nombre y lista de políticas activas |
| `trayectorias` | Por escenario, comuna y variable: tres listas (p10, p50, p90), una posición por año |
| `aportes` | Por escenario, comuna y variable: cuánto mueve cada política el valor final |
| `flujos` | Por escenario: hogares que se mudan entre dos comunas en un año |
| `impacto` | Por escenario: personas que viven en comunas sobre la norma anual de PM2,5 (p10, p50, p90 por año) |
| `validacion` | Error del modelo contra datos reales y contra alternativas simples |
| `promesas` | Comparación aparte (no es un interruptor): muchas promesas con poca ejecución contra pocas con mucha ejecución. Por paquete: valor de planilla, bandas, probabilidad de cumplir la norma por año. Ver `docs/promesas.md` |

Reglas del contrato:

- Solo se agregan claves; no se renombran ni se quitan sin avisar a quien hace la interfaz.
- Falta la variable `seguridad`, que se sumará cuando exista.

### Archivo real (v0, 21 nov)

`viz/datos/simulacion.json`, generado con `make simulate` (calibración, promesas y simulación, en ese orden; determinista: la
misma corrida da el mismo archivo). Diferencias con el ejemplo que la interfaz debe saber:

- **La variable es `pm25_anual`, no `pm25_invierno`.** El modelo v0 es anual. La interfaz
  debe leer los ids desde `variables`, no fijarlos en el código.
- Los códigos de comuna son los oficiales de cinco dígitos (`"13101"` es Santiago).
- Claves nuevas: `comunas[].zona_ppda` (A o B), `politicas[].tipo` (vigente o propuesta),
  `politicas[].procedencia`, `cita` y `efecto`, y `escenarios[].lectura`.
- **Los interruptores** son los escenarios con `lectura: "conservadora"`. Los escenarios
  `base-lectura-optimista` y `base-plan-escrito` son la misma combinación de políticas con
  otra lectura de la credibilidad; no son un interruptor.
- **Apagar una política vigente** significa que no avanza más desde 2023, no que la leña
  vuelva (`meta.significado_sin`).
- `flujos` viene vacío hasta que exista el mecanismo de hogares.
- Los códigos de comuna del ejemplo son nombres en minúsculas. El archivo real usará el
  código oficial de comuna; la interfaz no debe depender del formato del código.

## Frentes de trabajo

Cada frente tiene una entrada, una salida y una forma de saber que terminó. El frente 6 es el
código de la simulación en `core/` (no un LLM) y tiene un solo dueño.

| Frente | Qué construye | Entrega | Depende de | Estado | Quién |
|---|---|---|---|---|---|
| 1. Datos de aire | Mediciones de PM2,5 por estación, 2017 a 2024 | `data/aire/*.csv` | Nada | Hecho |  |
| 2. Emisiones y comunas | Emisiones por comuna y fuente; tabla de las 52 comunas | `data/emisiones/`, `data/comunas_rm.csv` | Nada | Hecho |  |
| 3. Censo y mudanzas | Las dos matrices de mudanza entre comunas (2012 a 2017 y 2019 a 2024) y viviendas por comuna | `data/censo/*.csv` | Nada | Por empezar | Massiel |
| 4. Seguridad | Delitos por comuna y año (CEAD) y victimización (ENUSC) | `data/seguridad/*.csv` | Nada | Delitos CEAD hechos; falta ENUSC |  |
| 5. Políticas y credibilidad | Catálogo cerrado de intervenciones con rangos citados; medidas del plan de aire y proyectos del SEIA clasificados; credibilidad por medida | `data/politicas/*.csv`, `docs/catalogo-intervenciones.md` | Nada | Inventario hecho (`docs/politicas-aire.md`); cumplimiento por capítulo hecho; falta catálogo de intervenciones |  |
| 6. Modelo | Aire acoplado por la cuenca; luego flujos de hogares por tipo; luego seguridad | `core/`, con pruebas | 1 y 2 para aire; 3 para hogares | Aire v0 hecho y escribe `simulacion.json`; falta v1 de aire y hogares | Jesús |
| 7. Validación y experimentos | Ajuste y prueba separados, comparación con alternativas simples, réplicas | `results/`, y escribe `simulacion.json` real | 6 | Por empezar |  |
| 8. Interfaz | Mapa de la región, control de tiempo, interruptores de políticas, ficha de comuna | `viz/` | Solo el contrato | Puede empezar hoy | Gabriel |
| 9. Spec, README y pitch | `sim-spec.md` completo, guion de demo, textos de entrega | `docs/`, `README.md` | Avanza con todos | Por empezar |  |

Los frentes 3, 4 y 5 no dependen de nadie y el modelo los necesita. Son los mejores para
tomar ahora.

## Por dónde empieza cada uno

### Jesús: frente 6, el modelo

Es el código de la simulación en `core/`. Orden de construcción:

1. **Aire acoplado por la cuenca.** Entradas ya disponibles en `data/aire/` (mediciones por
   estación) y, cuando termine el frente 2, `data/emisiones/` y `data/comunas_rm.csv`.
   `experiments/prueba_brecha.py` tiene una versión de tamizaje del acople entre comunas
   que sirve como punto de partida, no como modelo final.
2. **Flujos de hogares por tipo**, cuando Massiel entregue las matrices del censo.
3. **Seguridad**, solo si queda tiempo.

Lo primero que necesita la interfaz es que el modelo escriba `simulacion.json` con la
forma del contrato de arriba, aunque sea solo con aire.

### Massiel: frente 3, censo y mudanzas

Entrega tablas limpias en `data/censo/`, con el script de descarga en `datos/censo/` y un
README con fuente, fecha y vacíos:

1. **Matriz de mudanzas 2019 a 2024**: del Censo 2024, comuna de residencia actual contra
   comuna de residencia hace 5 años, para las 52 comunas de la región.
2. **Matriz de mudanzas 2012 a 2017**: lo mismo del Censo 2017.
3. **Viviendas y población por comuna** en ambos censos, para el tope de viviendas.

Formato sugerido de cada matriz: una fila por par, con columnas `codigo_origen`,
`codigo_destino`, `personas`. Los códigos de comuna son los de cinco dígitos (13101 es
Santiago), los mismos que usa `viz/public/geo/comunas_rm.geojson`.

Por comprobar al empezar: si el INE publica esas matrices ya tabuladas por comuna o hay
que construirlas desde los microdatos.

### Gabriel: frente 8, la interfaz

Trabaja en la rama `feat/viz-interfaz` con el ejemplo de `viz/ejemplo/simulacion.json`.


## Resultado de la prueba de la brecha (21 nov)

Se corrió `python -m experiments.prueba_brecha` con emisiones 2023 del RETC y las medias
anuales de 10 estaciones. Es un modelo de tamizaje, no el modelo final.

| Escenario | Cambio medio (µg/m³) | Brecha entre comunas | Orden conservado (Spearman) |
|---|---|---|---|
| Leña -50 % en toda la región | -5,7 | 18,1 → 14,4 | 0,97 |
| Transporte -20 % en toda la región | -1,8 | 18,1 → 16,2 | 0,99 |
| Todas las fuentes -20 % | -4,3 | 18,1 → 14,5 | 1,00 |
| Cierra la industria de Renca | -0,2 | 18,1 → 17,9 | 1,00 |
| Proyecto nuevo de 108 t/año en Tiltil | +0,2 | 18,1 → 18,3 | 1,00 |
| Sin leña en las 5 comunas que más emiten | -4,4 | 18,1 → 15,8 | 0,98 |

Qué significa:

- **El orden entre comunas casi no cambia.** El titular de la demo no puede ser "el ranking
  se reordena". Pasa a ser la trayectoria de cada comuna y de qué depende.
- **Los proyectos locales pesan muy poco** (±0,2 µg/m³). Un proyecto del SEIA como shock de
  la demo no se va a notar.
- **La leña es la palanca**: es el 60 % de las emisiones reguladas (leña, transporte,
  industria).

Cuánto confiar: poco. El ajuste explica el 55 % de la diferencia entre estaciones, eligió
la escala máxima permitida (40 km, toda la cuenca como una sola caja) y las emisiones no
calzan con lo medido: la leña se quema en la periferia (Paine, Lampa, Buin) y el aire peor
está en El Bosque, Cerro Navia y Pudahuel. **Un acople solo por distancia no alcanza como
modelo de aire**; faltan relieve y viento.

### Hallazgo para la demo: la leña y la Zona B

El plan de descontaminación prohíbe la leña en la Zona A (34 comunas urbanas, art. 74). En
la Zona B (18 comunas periféricas, 15 % de la población) solo restringe los calefactores
nuevos (art. 75). Según el RETC 2023, el **77 % de las emisiones de leña está en la Zona B**
(2.487 de 3.218 t).

Pregunta candidata para la demo: **¿qué pasa si la prohibición se extiende a la Zona B?**
Es una decisión real que no se puede ensayar, y muestra interacción: comunas urbanas
mejoran por una medida que se ejecuta en otras. La magnitud no se puede afirmar con el
modelo de tamizaje. Detalle de zonas y artículos en `docs/politicas-aire.md`.

### Credibilidad: hay datos por capítulo del plan

El informe de avance de la SMA 2024 agrega por categoría; el detalle por medida está en un
anexo Excel que no se pudo obtener. La revisión encargada por la SEREMI RM (ECOS-Chile,
2023) resume 157 medidas (24 % conformes, 21 % parciales, 55 % sin evidencia pública), pero
el documento publicado solo nombra seis por código. Lo que sí trae, con página y cita, es el
cumplimiento por capítulo, que calza con las fuentes del modelo:

| Fuente | Medidas evaluadas | Conformes | Parciales | Sin evidencia |
|---|---|---|---|---|
| Transporte (fuentes móviles) | 31 | 7 | 19 | 5 |
| Industria (fuentes estacionarias) | 58 | 10 | 5 | 43 |
| Leña | 23 | 4 | 7 | 12 |
| Episodios críticos | 33 | 12 | 5 | 16 |

Tabla completa en `data/politicas/cumplimiento_ppda_capitulos.csv`. Alcanza para una
credibilidad por tipo de fuente con datos reales; no para una credibilidad medida por
medida. "Sin evidencia" significa que no hubo evidencia pública para comprobarla, no
incumplimiento demostrado.

### Seguridad: datos disponibles

`data/seguridad/delitos_comuna_anio.csv`: casos policiales y tasa por 100.000 habitantes del
CEAD, 52 comunas, 17 categorías, 2017 a 2024. `dmcs_total` es una suma propia de 11
categorías publicadas, porque el portal no entrega esa fila; la composición está en
`data/seguridad/README.md`. No incluye victimización (ENUSC).

## Orden y cortes

1. **Aire acoplado** es el núcleo. Sin esto no hay demo.
2. **Flujos de hogares por tipo**, calibrados con las matrices del censo.
3. **Seguridad** es lo primero que se recorta si falta tiempo.

Hay una prueba pendiente que define el titular de la demo
(`python -m experiments.prueba_brecha`, necesita el frente 2): mide si las políticas
cambian la brecha entre comunas o las mueven a todas por igual. La interfaz es la misma
en ambos casos; cambia si el mensaje es "el ranking se reordena" o "la trayectoria de tu
comuna y de qué depende".

## Frente 8, en detalle

Pantalla única, sin registro ni pasos previos.

- **Mapa** de la Región Metropolitana a pantalla completa, con las comunas coloreadas por
  la variable elegida.
- **Control de tiempo** abajo, de 2026 a 2036. Al moverlo cambia el mapa.
- **Panel de políticas** a un lado: cada política con su interruptor y su barra de
  credibilidad. Apagar una cambia de escenario.
- **Ficha de comuna** al hacer clic: banda de proyección, tres hallazgos en lenguaje
  simple y qué política mueve el resultado (`aportes`).
- **Perfil del hogar** arriba: elegir un tipo o mover los pesos reordena la lista de
  comunas al instante.
- **Mudanzas** como arcos entre comunas (`flujos`).
- **Incertidumbre visible**: la banda p10 a p90 se muestra siempre, nunca un número solo.

Pendientes propios de este frente:

- Conseguir los polígonos de las 52 comunas en GeoJSON, de una fuente oficial y con su
  licencia anotada.
- Elegir la librería de mapa. Sugerencia: deck.gl sobre MapLibre.
- `viz/README.md` pide TypeScript y, si hay simulación en el navegador, un Web Worker.
  Aquí no hay simulación en el navegador: solo se lee el JSON.

## Reglas comunes

- Ramas `feat/<rol>-<tema>` y PR a `main` (ver `work-plan.md`).
- Scripts de descarga en `datos/`, archivos descargados en `data/raw/`, tablas limpias en
  `data/`. Cada carpeta de datos lleva un README con fuente, fecha y vacíos conocidos.
- Ningún número inventado en `data/`. Lo que falte queda vacío y anotado.
- `data/raw/` puede pesar cientos de megas: decidir si va al repo antes del primer commit.
