# root

<img src="./project-logo.png" alt="Logo de root" width="160" />

Platanus Hack 26 · Santiago · team-22 · Track 🌐 Simulaciones

**¿Hacia dónde va una comuna, y qué pasa si el plan que la iba a mejorar no se cumple?**

root simula cómo evolucionan las 52 comunas de la Región Metropolitana de Santiago entre 2026 y 2036
y las ordena por el riesgo que corre quien quiere vivir, invertir o instalar una empresa en ellas.
Cada plan público pesa según **la probabilidad real de que se cumpla**, y cada resultado se muestra
como una banda de 500 réplicas, nunca como un número solo.

**[Probar root](https://root-landing.onrender.com)**

Qué simula y qué mide:

- **Aire.** PM2,5 por comuna y año según los planes de descontaminación, con el aire moviéndose
  por la cuenca de una comuna a otra.
- **Hogares y población.** Quién se muda a dónde y cuánto crece cada comuna; los hogares se
  llevan consigo la leña que queman.
- **Seguridad.** Delitos por habitante, con el efecto de cámaras e iluminación como políticas
  ilustrativas.
- **Clima.** Cambio en la frecuencia de sequía por comuna, con las corridas de los modelos
  climáticos de ARClim.
- **Agua.** Caudal medido en 14 estaciones de la DGA y un «¿y si sigue la megasequía?» que sortea
  500 décadas posibles por río.
- **Lo que mira quien invierte.** Decretos de escasez hídrica, capacidad de la red eléctrica,
  proyectos aprobados en el SEIA y licitaciones municipales, una por una.

Escribes tu caso con tus palabras y Claude lo traduce a prioridades dentro de un catálogo cerrado;
el orden de las comunas y todos los números los calcula siempre la simulación. El modelo se probó
contra datos que no había visto y publicamos también dónde pierde.

## La pregunta

**¿Qué pasa si el plan no se cumple?**

Cada medida del Plan de Descontaminación (PPDA, D.S. 31/2016) pesa según el historial de
cumplimiento de quien la ejecuta. Ese historial viene de una revisión medida por medida de
2023: 24 % conformes, 21 % parciales y 55 % sin evidencia pública. El modelo corre 500 réplicas
por escenario y muestra bandas, nunca un número solo.

## Hallazgos

PM2,5 en 2036, ponderado por población. Nivel de 2023: 23,1 µg/m³ (las 10 comunas con estación
parten de su medición). Norma anual: 20 µg/m³.

| Escenario | Mediana (p10–p90) |
|---|---|
| Ninguna política avanza | 22,9 |
| Planes vigentes, con el historial real de cumplimiento | **21,4** (20,2–22,4) |
| Planes vigentes, cumplidos al 100 % | **18,8** |
| Planes vigentes + prohibición de leña en la Zona B | 18,5 (15,6–21,1) |

1. **El incumplimiento como cifra.** El plan escrito deja la región bajo la norma. Con el
   cumplimiento observado no la alcanza.
2. **La migración puede borrar la mejora.** La ciudad se muda hacia la Zona B (+18 % de
   población en 2036). Si la leña sigue a la gente, con el plan vigente la región queda en 22,9,
   prácticamente el nivel de hoy.
3. **Importa más quién ejecuta que cuántas promesas hay.** Una planilla da 20,24 µg/m³ para
   todas las variantes de las 18 promesas de la Zona B. La simulación las separa:

   | Ejecución | Banda | Probabilidad de cumplir la norma |
   |---|---|---|
   | Un solo ejecutor | 2,96 µg/m³ | 0,51 |
   | 18 municipios | 1,32 µg/m³ | 0,54 |

   Lo robusto es la banda. La probabilidad de cumplir la norma depende de qué lado del umbral
   quede la mediana y su orden se invierte con cambios chicos de nivel (`docs/promesas.md`).
4. **Las políticas de seguridad casi no mueven la tasa comunal.** Con efectos citados de
   metaanálisis (cámaras y alumbrado reducen delitos contra la propiedad, no violentos),
   cobertura del 25 % y credibilidad municipal baja, las cámaras bajan los delitos de mayor
   connotación social entre 0,6 % y 1,0 % en las comunas intervenidas: muy dentro de la
   variación de un año a otro.

Detalle y supuestos: [`docs/modelo-aire.md`](docs/modelo-aire.md),
[`docs/modelo-hogares.md`](docs/modelo-hogares.md), [`docs/modelo-seguridad.md`](docs/modelo-seguridad.md),
[`docs/promesas.md`](docs/promesas.md).

## Validación

Cada mecanismo se ajusta con un período y se prueba con otro que no vio, contra alternativas
simples. También publicamos dónde pierde.

<!-- validacion:inicio (generado por make validate) -->
| Variable | Prueba fuera de muestra | Métrica | Modelo | Sin cambio | Tendencia | Cobertura banda 80 % | Gana |
|---|---|---|---|---|---|---|---|
| Aire | PM2,5 por estación 2022-2024 desde 2019 (ajuste 2017-2019) | RMSE µg/m³ | 1,91 | 2,40 | 4,24 | 74% | **Modelo** |
| Hogares | Migración neta por comuna 2019-2024 (ajuste 2012-2017) | RMSE personas | 4.335 | 7.716 | 5.054 | — | **Modelo** |
| Población | Población por comuna 2024 desde 2017 (tasas 2012-2017) | RMSE personas | 16.904 | 15.046 | — | — | Sin cambio |
| Seguridad | Tasa de delitos 2024 a 1 año (comunas fuera del ajuste) | RMSE log (≈ error relativo) | 0,085 | 0,074 | 0,131 | 70% | Sin cambio |
| Seguridad | Tasa de delitos 2024 a 2 años (comunas fuera del ajuste) | RMSE log (≈ error relativo) | 0,108 | 0,124 | — | 66% | **Modelo** |
<!-- validacion:fin -->

Un solo comando reproduce la tabla: `make validate` (recalibra y escribe
[`docs/validacion.md`](docs/validacion.md) y `results/validacion.json`). Las alternativas
son **sin cambio** (se repite el último valor) y **tendencia** (sigue la línea del ajuste).

El modelo de aire acierta cuánto mejora la región, pero todavía **no qué comunas ganan más**.
Donde hay estación (10 comunas), el nivel parte de lo medido y el modelo calcula el cambio.
Más detalle en [`docs/sim-spec.md`](docs/sim-spec.md#validación).

## Decisiones técnicas

Los números salen del Monte Carlo, no de un modelo de lenguaje. La IA cumple un solo papel: leer el caso
que la persona escribe («mi hijo tiene asma», «quiero instalar una bodega») y elegirle un perfil y unos
pesos dentro de un **catálogo cerrado**. Nunca escribe cifras sobre las comunas.

Para eso usamos **Claude Sonnet 5.5 por la API de Anthropic**, con salida estructurada (`json_schema`),
validación en el servidor (se descarta toda variable fuera del catálogo y toda cita que no esté textual en
el caso), esfuerzo bajo y caché de prompt y de respuestas. Resultado con el modelo real: **29 de 29**
frases de prueba quedan como se esperaba, incluida una inyección de prompt
([`docs/evaluacion-casos.md`](docs/evaluacion-casos.md)).

Evaluamos las alternativas y las descartamos a propósito:

| Alternativa | Por qué no |
|---|---|
| IA local (modelo abierto servido con llama-server, Ollama o vLLM) | Desplegarla exige un servidor con GPU encendido todo el día, o una CPU demasiado lenta para responder en el momento. Con la API, el servidor es un proceso Node pequeño sin GPU, se paga solo por llamada y un tope diario fija el gasto máximo. Además, un modelo pequeño entiende peor los casos ambiguos o en otro idioma. |
| Fine-tuning (LoRA/QLoRA o por API) | No existen casos etiquetados; habría que inventarlos (dataset sintético, riesgo de colapso de modo). El catálogo cambió varias veces en 36 horas (de 3 a 7 variables, de 5 a 9 perfiles) y cada cambio obligaría a reentrenar. Con prompt + esquema, se edita y se reevalúa en minutos con `npm run evaluar`. |
| RAG sobre documentos de las comunas | El LLM terminaría citando cifras; los números deben venir solo del simulador validado. |
| Agentes LLM dentro de la simulación | 500 réplicas × 52 comunas × 10 años = 260 000 decisiones por escenario, no reproducibles por semilla y sin datos para validarlas. Los hogares se modelan como flujos calibrados con el censo ([ADR-0002](docs/adr/0002-hogares-como-flujos-agregados.md)). |

La clave de Anthropic vive solo en `servidor-guia/`, con tope por IP y tope diario. Si el servidor no
responde, la página sigue funcionando con detección por palabras clave. Detalle en
[ADR-0007](docs/adr/0007-claude-sin-fine-tuning.md); todas las decisiones de ingeniería (modelo,
validación, despliegue, seguridad, reproducibilidad) en [`docs/decisiones-tecnicas.md`](docs/decisiones-tecnicas.md).

## Cómo ejecutar

```bash
make setup      # crea .venv e instala dependencias
make test       # 329 pruebas del núcleo y de los datos
make simulate   # calibra, simula y escribe viz/datos/simulacion.json (~15 s)
make validate   # prueba fuera de muestra contra sin cambio y tendencia -> docs/validacion.md
make licitaciones-detalle  # aporte de cada licitación a la credibilidad municipal -> viz/datos/licitaciones.json
```

El sitio publicado es la landing de `web/` con la interfaz de `viz/` dentro, en `simulador/`: `npm run build`
en `web/` construye las dos. Para ver solo el resultado en el mapa en relieve (la interfaz de `viz/`):

```bash
cd viz
npm install     # hace falta de nuevo si cambió package-lock.json
npm run dev     # abre la dirección que imprime, normalmente http://localhost:5173
```

El mapa en relieve necesita internet y WebGL; si falta alguno, la interfaz pasa sola al mapa plano
(detalle y respaldos sin conexión en [`viz/README.md`](viz/README.md)).

Para volver a descargar los datos crudos: `pip install -e ".[datos]"` y correr el script de
`datos/` de cada fuente (ver «Fuentes de datos»).

## Estructura

```
datos/        scripts de descarga (SINCA, RETC, censo, CEAD, PPDA)
data/         tablas limpias, con README de fuente, fecha y vacíos
core/         núcleo sin interfaz: aire, hogares, credibilidad y ciclo anual
experiments/  calibración, comparación de promesas y simulación
results/      resultados de validación, cada uno con el comando que lo reproduce
viz/          interfaz: solo lee viz/datos/simulacion.json
docs/         spec, modelo y decisiones del proyecto
```

## Fuentes de datos

- SINCA (MMA): PM2,5 por estación.
- RETC: emisiones por comuna y fuente.
- INE: Censos 2017 y 2024.
- CEAD: delitos por comuna.
- ECOS-Chile y la SMA: cumplimiento del PPDA.

Cada una con su URL, fecha de descarga y vacíos en el README de su carpeta de `data/`. Las
emisiones todavía no tienen README: su fuente (datos abiertos del RETC) está documentada en
`datos/emisiones/build_emisiones.py`.

## Equipo

- Jesus Rodolfo Gil Farias ([@Jrgil20](https://github.com/Jrgil20))
- Gabriel David Castellano Sierra ([@GdCastellano](https://github.com/GdCastellano))
- Daniel Enrique Bruno Silva ([@Holeekey](https://github.com/Holeekey))
- Valeria Riera ([@ingvaleriariera](https://github.com/ingvaleriariera))
- Massiel Paola Perozo Ballestero ([@massiperozo](https://github.com/massiperozo))

Documentos del equipo: [`docs/plan-comunas.md`](docs/plan-comunas.md) ·
[`docs/contexto-proyecto.md`](docs/contexto-proyecto.md) · [`docs/work-plan.md`](docs/work-plan.md)
