# Modelo de seguridad

Estado al 21 de noviembre de 2026. Mecanismo 3 del modelo (ver
[`contexto-proyecto.md`](./contexto-proyecto.md), sección 4). Código en `core/seguridad.py`;
validación en `experiments/calibrar_seguridad.py`; resultados en
`results/seguridad_calibracion.json`. Datos: delitos por comuna del CEAD en
`data/seguridad/` (ver su README).

Reproducir:

```
python -m experiments.calibrar_seguridad
```

## Variable

**Delitos de mayor connotación social (DMCS) por 100.000 habitantes**, la tasa que publica el
CEAD (casos policiales). Se separa en dos grupos según lo que respalda la evidencia:

| Grupo | Componentes de los DMCS | Parte de los DMCS (mediana 2024) |
|---|---|---|
| Propiedad | Robos en lugar habitado y no habitado, robo de vehículo, otros robos con fuerza, hurtos | 35 % |
| Violentos | Homicidios, lesiones, violaciones, robos con violencia o por sorpresa, violencia intrafamiliar | 65 % |

La población no entra al mecanismo (regla del contexto): la tasa es la del CEAD, no se
recalcula con la población simulada.

## Ecuaciones

Inercia, por comuna `c` y grupo `g`, sobre el logaritmo de la tasa:

```
x[t+1] = μ[c, g] + φ[g] · (x[t] − μ[c, g]) + σ[g] · ε[t, c, g]
```

- `μ[c, g]`: media de largo plazo de la comuna, con los años 2017, 2018, 2022, 2023 y 2024.
- `φ`, `σ`: ajustados con los pares de años 2017→2018, 2022→2023 y 2023→2024.
- **Años atípicos fuera**: 2019 (estallido), 2020 y 2021 (pandemia), como pide el contexto.

Intervenciones: una medida en la comuna `c`, con cobertura `k` (parte de los delitos de la
comuna que ocurre en los lugares intervenidos) y avance `p` (de 0 a 1, según la credibilidad):

```
comuna intervenida:  tasa × (1 − k · p · r[g])
comunas vecinas:     tasa × (1 − s · k · p · r[g])
```

- `r[g] = 1 − 1/OR[g]`: reducción en el área intervenida, **derivada** de la razón de odds del
  metaanálisis y sorteada una vez por réplica desde su intervalo de confianza.
- `s`: parte del efecto que llega a las comunas vecinas, sorteada una vez por réplica.
  Negativo es desplazamiento; positivo, difusión de beneficios.

## Catálogo de intervenciones

Cifras leídas en los textos primarios.

| Intervención | Fuente | Total | Propiedad | Violentos |
|---|---|---|---|---|
| Cámaras (CCTV) | Piza, Welsh, Farrington y Thomas (2019), *Criminology & Public Policy* 18:135–159, pág. 141, tabla 1 y fig. 2 | OR 1,141 (IC 95 % 1,072–1,215): «Crime decreased by approximately 13%» | OR 1,161 (1,023–1,317) | OR 1,050 (0,954–1,155), no significativo |
| Iluminación | Welsh, Farrington y Douglas, informe Brå (2021), págs. 33–35, tabla 2 (publicado en *Criminology & Public Policy*, 2022) | RES 1,16 (IC 90 % 1,06–1,27): «crimes decreased by 14%» | RES 1,14 (1,03–1,27) | RES 0,99 (0,87–1,13), no significativo |

- Los efectos son **en el área intervenida** (un estacionamiento, una cuadra), no en una
  comuna entera. Por eso cada política declara su **cobertura**.
- Los violentos se sortean desde su intervalo, que incluye «sin efecto»: no se les atribuye una
  reducción que la evidencia no muestra.
- Las cámaras con monitoreo activo rinden más (OR 1,172; IC 1,080–1,272) y las pasivas no
  tienen efecto significativo (OR 1,015). Las políticas del modelo suponen monitoreo activo
  pero usan los rangos por tipo de delito, porque el artículo no los cruza.
- **Ningún estudio es chileno** (contexto §4): los rangos son bandas, no promesas.

## Supuestos fijados antes de ver resultados

| Supuesto | Valor | Por qué |
|---|---|---|
| Cobertura de cada política | 25 % de los delitos contra la propiedad de la comuna | Decisión del escenario: es parte de la definición de la política, no un dato |
| Credibilidad municipal | Prior: media 0,35, concentración 4 (banda ancha), actualizado con las licitaciones 2024 de cada municipalidad (ChileCompra: adjudicadas / cerradas, tamaño efectivo máximo 40) | El prior toma como referencia la tasa observada del PPDA. La tasa de adjudicación es un **proxy** de capacidad de ejecución municipal, no prueba de que un plan de seguridad se cumpla. En las 5 comunas intervenidas la media sube a 0,79–0,85 (`politicas[].credibilidad_por_comuna`) |
| Efecto sobre vecinas | `s` entre −0,1 y +0,2, comunas a menos de 6 km (centroides) | Bowers et al. (2011) encuentran que la difusión es más probable que el desplazamiento, pero en áreas de unos cientos de metros: se cita solo para el signo. No hay polígonos de comunas en el repo, así que la vecindad es por distancia |
| Rampa | 10 años de ejecución para el efecto completo | Igual que en el aire, para que la credibilidad signifique «fracción cumplida» |

## Validación

Comunas completas fuera del ajuste (contexto §6): para cada comuna, `φ` y `σ` se ajustan con
las otras 51 (pares 2017→2018 y 2022→2023) y se predice su tasa DMCS de 2024.

| Error relativo en 2024 | A 1 año (desde 2023) | A 2 años (desde 2022) |
|---|---|---|
| **Modelo** | 8,5 % | **10,8 %** |
| Todo sigue igual (persistencia) | **7,4 %** | 12,4 % |
| Sigue la tendencia 2022→2023 | — | 13,1 % |
| Media prepandemia 2017–2018 | 20,0 % | 20,0 % |
| Valores reales dentro de la banda del 80 % | 70 % | 66 % |

Qué significa:

- **A un año el modelo pierde contra «todo sigue igual»; a dos años le gana a todas las
  alternativas.** Para proyectar a 5 y 10 años importa más el segundo resultado, pero el
  primero se dice.
- **Las bandas son algo estrechas** (70 % y 66 % en lugar de 80 %). No es un shock común a la
  región (el sesgo medio es −2 % en propiedad y +3 % en violentos): en los violentos el modelo
  subestima la variabilidad (0,080 ajustado contra 0,100 observado en la prueba). No se corrigió
  con los datos de prueba.
- **Los efectos de las intervenciones no se pueden validar localmente**: no hay datos de cámaras
  ni de iluminación por comuna. Vienen de los metaanálisis y se presentan como rangos.

## En la simulación 2026–2036

`make simulate` agrega la variable `seguridad` (DMCS por 100.000 habitantes) a
`viz/datos/simulacion.json`, con banda p10–p90 en cada escenario. Hay dos políticas
**ilustrativas** con su interruptor (`con-ilustrativa-camaras`, `con-ilustrativa-iluminacion`):
todavía no hay planes comunales de seguridad clasificados, así que actúan, con una regla fija,
en las 5 comunas de mayor tasa DMCS 2024 (Santiago, Providencia, Estación Central, La Cisterna y
Cerrillos). Cada municipio es su propio ejecutor: sus medidas fallan juntas.

Aporte de cada política en 2036 (mediana de la diferencia pareada por réplica, misma semilla):

| Política | En las comunas intervenidas | En las comunas vecinas |
|---|---|---|
| Cámaras con monitoreo activo | −1,8 % a −2,4 % de la tasa DMCS | Hasta −10,3 casos por 100.000 (San Miguel) |
| Iluminación | −0,9 % a −1,7 % | Hasta −3,2 casos por 100.000 (San Miguel) |

Con la credibilidad municipal actualizada por ChileCompra (media 0,79–0,85 en vez del supuesto
0,35), el efecto es unas 2,5 veces el de la versión anterior (−0,6 % a −1,0 % y −0,2 % a −0,6 %).

Qué significa:

- **Con estos supuestos, las políticas de seguridad casi no mueven la tasa comunal**: el efecto
  queda muy dentro de la banda de un año a otro (en Providencia, la banda 2036 sin políticas va
  de 5.982 a 7.738). Es la combinación de tres cosas que el modelo no esconde: solo los delitos
  contra la propiedad responden (35 % de los DMCS), la cobertura es 25 % y la ejecución es
  gradual (10 años). Con la credibilidad actualizada por ChileCompra (media cercana a 0,83) el
  efecto crece, pero sigue siendo chico frente a la banda.
- Sí existe interacción entre comunas: las vecinas reciben parte del efecto, con signo abierto.
- Para la demo, la lectura honesta es «cuánto haría falta»: con cobertura 25 % y la ejecución
  municipal esperada, una política de cámaras no se nota en la tasa comunal. No se subió la
  cobertura después de ver el resultado.
- Las tasas de largo plazo vuelven hacia la media de cada comuna (que incluye los años
  prepandemia, más altos): por eso varias comunas suben respecto de 2024 aun sin políticas.
