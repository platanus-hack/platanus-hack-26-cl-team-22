# Decisiones técnicas

Resumen de las decisiones de ingeniería del proyecto, con lo que evaluamos y por qué lo descartamos. El
detalle de cada una está en su ADR (`docs/adr/`) o en el documento de modelo que se enlaza.

## 1. Los números salen del simulador, nunca de un modelo de lenguaje

**Decisión:** todo valor sobre una comuna (PM2,5, hogares, seguridad, agua, clima) sale del Monte Carlo de
`core/`, que se valida fuera de muestra (`make validate`, [`validacion.md`](validacion.md)). La IA solo
interpreta el caso que escribe la persona.

**Por qué:** si un LLM escribiera cifras, el resultado dejaría de ser reproducible y perdería la validación.
Esta regla es la que descarta RAG y agentes LLM (ver punto 5).

## 2. Monte Carlo con credibilidad, no promesas al pie de la letra

**Decisión:** cada medida de un plan tiene una probabilidad anual de ejecutarse,
`θ ~ Beta(α0 + k, β0 + n − k)`, con una previa por tipo de ejecutor y su historial de `k` hitos cumplidos de
`n`. Cada una de las 500 réplicas sortea qué se ejecuta cada año, y el resultado se muestra como banda p10–p90.
Detalle en [`credibilidad.md`](credibilidad.md).

**Alternativa descartada:** suponer que el plan se cumple entero. La revisión del PPDA de 2023 encontró 24 %
de medidas conformes y 55 % sin evidencia pública; un escenario determinista sería optimista por construcción.

## 3. Hogares como flujos agregados, no miles de agentes

**Decisión:** las mudanzas entre comunas son flujos calibrados con las matrices de migración de los censos
2017 y 2024, y llevan consigo la calefacción a leña. Ver [ADR-0002](adr/0002-hogares-como-flujos-agregados.md)
y [`modelo-hogares.md`](modelo-hogares.md).

**Alternativas descartadas:**

| Opción | Por qué no |
|---|---|
| ABM con miles de agentes sintéticos | No hay datos individuales para calibrarlos; los flujos agregados se validan directo contra el censo |
| Agentes LLM que deciden mudarse | 500 réplicas × 52 comunas × 10 años = 260 000 decisiones por escenario, sin semilla reproducible y sin datos para validarlas |

La pestaña Social suma una simulación por agentes de saturación y derrame
([`modelo-mudanzas-abm.md`](modelo-mudanzas-abm.md)): sus agentes siguen reglas, no un LLM, y corre en un
Web Worker con un PRNG con semilla.

## 4. Validación contra alternativas ingenuas

**Decisión:** cada mecanismo se ajusta con un período y se prueba con otro, contra dos alternativas:
**sin cambio** (se repite el último valor) y **tendencia** (sigue la línea del ajuste). La tabla del README
la genera `make validate`; no se edita a mano.

**Por qué:** un modelo que no le gana a «sin cambio» no aporta. Publicamos también dónde todavía no gana
(el aire acierta cuánto mejora la región, pero no qué comunas ganan más).

## 5. Claude por la API, con catálogo cerrado

**Decisión:** Claude Sonnet 5.5 (`servidor-guia/`) convierte el caso («mi hijo tiene asma») en un perfil y
unos pesos dentro del catálogo de `viz/src/lib/caso.ts`. Ver [ADR-0007](adr/0007-claude-sin-fine-tuning.md).

Cómo se acota:

- **Salida estructurada** (`json_schema`): la respuesta solo puede nombrar perfiles y variables del catálogo.
- **Validación en el servidor:** se descarta toda variable o grado fuera del catálogo y todo ajuste cuya cita
  no aparezca textual en el caso.
- **Evaluación con el modelo real:** `npm run evaluar` corre 29 frases con resultado esperado, incluidas una
  inyección de prompt, una en inglés y una de una sola palabra
  ([`evaluacion-casos.md`](evaluacion-casos.md)).
- **Respaldo sin IA:** si el servidor falla, la página usa detección por palabras clave.

**Alternativas descartadas:**

| Opción | Por qué no |
|---|---|
| IA local (modelo abierto con llama-server, Ollama o vLLM) | Exige un servidor con GPU encendido todo el día, con costo fijo aunque nadie use la app, o una CPU demasiado lenta para responder en el momento. Un modelo pequeño entiende peor los casos ambiguos o en otro idioma |
| Fine-tuning (LoRA/QLoRA o por API) | No existen casos etiquetados; habría que inventarlos (dataset sintético, riesgo de colapso de modo). El catálogo cambió varias veces en 36 horas (de 3 a 7 variables, de 5 a 9 perfiles) y cada cambio obligaría a reentrenar |
| RAG sobre documentos de las comunas | El LLM terminaría citando cifras de comunas (rompe el punto 1) |
| Solo palabras clave | Falla con «casa matriz», «departamento de logística» o negaciones. Se mantiene como respaldo |

## 6. Despliegue: sitio estático + un proceso Node pequeño

**Decisión:** el sitio (landing y simulador) es un solo bundle estático (`web/` incluye `viz/` al compilar).
El único proceso con servidor es `servidor-guia/`, Node que ejecuta TypeScript sin paso de compilación.
`render.yaml` despliega ambos; `vercel.json` publica solo el sitio.

**Por qué es barato:**

- El navegador **no recalcula el modelo**: lee contratos JSON precalculados (`viz/datos/*.json`). No hay
  backend de simulación que escalar.
- No hay GPU: el costo de IA es por llamada, y `TOPE_DIARIO` fija el máximo de llamadas por día para todo el
  servicio.
- Gasto acotado por diseño: esfuerzo bajo (es una clasificación), caché de prompt de sistema, respuestas en
  memoria por 6 horas para pedidos idénticos y una sola llamada compartida para pedidos simultáneos iguales.
- Cada llamada deja una línea de log con sus tokens (sin el texto de la persona), para medir el costo real.

## 7. La clave de la API nunca llega al navegador

**Decisión:** `ANTHROPIC_API_KEY` vive solo en `servidor-guia/`, nunca en una variable `VITE_*` (Vite las
copia al código que descarga el navegador).

Protecciones del servidor ([`servidor-guia/README.md`](../servidor-guia/README.md)):

- Validación del pedido antes de llamar a Claude (400 si es inválido, 413 sobre 8 KB).
- 20 llamadas por minuto por dirección, con la IP real detrás del proxy (`PROXIES_CONFIABLES`).
- Tope global diario; al pasarlo responde 429 y la página sigue sin IA.
- Tiempo máximo de 20 s con un reintento; la llamada se corta si la página se va.
- El caso va entre comillas triples y se neutralizan las comillas internas, para que nadie cierre el bloque
  y escriba instrucciones.

## 8. Reproducible por semilla

**Decisión:** toda la aleatoriedad pasa por generadores con semilla: flujos `numpy.random.Generator` por
réplica en `core/credibilidad.py` y un PRNG propio en la interfaz (`viz/src/lib/prng.ts`); nunca
`Math.random()`. Cada número de `results/` sale de un comando con nombre en el script que lo produce.

**Límite conocido:** la interpretación de Claude no es reproducible bit a bit, pero solo mueve pesos dentro
del catálogo, y la persona los ve y puede apagarlos. El ranking y las bandas sí son reproducibles.

## 9. Pruebas y CI

- Python: pytest en `tests/` (calibración, validación y modelos).
- Interfaz: Vitest junto al código en `viz/src/lib/*.test.ts`; la lógica vive en funciones puras para poder
  probarla sin el navegador.
- Servidor: `node --test` con un Claude simulado, sin clave.
- CI (`.github/workflows/ci.yml`) corre `ruff check .` y `pytest` en cada PR.

## Índice de ADRs

| ADR | Decisión |
|---|---|
| [0001](adr/0001-shock-de-la-demo.md) | El shock de la demo es la leña del plan de descontaminación |
| [0002](adr/0002-hogares-como-flujos-agregados.md) | Los hogares se modelan como flujos agregados entre comunas |
| [0003](adr/0003-usuario-municipio-y-perfiles.md) | El municipio simula; el ciudadano lee con perfiles (reemplazado por 0006 en el usuario principal) |
| [0004](adr/0004-metrica-personas-sobre-la-norma.md) | La métrica de impacto es personas expuestas sobre la norma de PM2,5 |
| [0005](adr/0005-comunas-destacadas.md) | El motor simula las 52 comunas; la interfaz destaca 5 con estación |
| [0006](adr/0006-usuario-inversionista.md) | El usuario principal es el inversionista |
| [0007](adr/0007-claude-sin-fine-tuning.md) | Claude interpreta el caso con un catálogo cerrado, sin fine-tuning |
