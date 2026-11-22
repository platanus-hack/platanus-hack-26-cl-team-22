# ADR-0007: Claude interpreta el caso con un catálogo cerrado, sin fine-tuning

- **Estado**: Aceptado
- **Fecha**: 2026-11-22

## Contexto

La persona escribe su caso con sus palabras («mi hijo tiene asma», «quiero instalar una bodega») y la
app tiene que convertirlo en pesos para el índice de riesgo. Ese paso es una clasificación: elegir uno de
nueve perfiles y ajustar a lo más siete variables con cinco grados posibles (0, 3, 5, 8, 10).

Los números sobre las comunas salen del modelo de Monte Carlo (`core/`), no del modelo de lenguaje. Si un
LLM escribiera cifras, el simulador perdería su validación fuera de muestra.

## Decisión

Claude Sonnet 5.5 lee el caso en `servidor-guia/` con:

- **Salida estructurada** (`json_schema`): la respuesta solo puede nombrar perfiles y variables del
  catálogo de `viz/src/lib/caso.ts`.
- **Validación en el servidor** (`validarInterpretacion`): se descarta todo ajuste cuya variable o grado no
  esté en el catálogo, o cuya cita no aparezca textual en el caso.
- **Esfuerzo bajo, caché de prompt y caché de respuestas**: es una clasificación corta; el prompt de
  sistema se cachea y los casos repetidos no gastan una llamada.
- **Evaluación con el modelo real** (`npm run evaluar`, resultado en `docs/evaluacion-casos.md`): 29 frases
  con resultado esperado, incluidas una inyección de prompt, una en inglés y una de una sola palabra.

## Alternativas consideradas

| Opción | Pros | Contras | Por qué se descartó |
|---|---|---|---|
| Fine-tuning (LoRA/QLoRA o API) | Menos tokens por llamada; estilo fijo | Necesita cientos de casos etiquetados que no existen; habría que inventarlos (dataset sintético, riesgo de colapso de modo); cada cambio del catálogo obliga a reentrenar; el modelo ajustado puede seguir saliéndose del catálogo | El catálogo cambió varias veces en 36 horas (de 3 a 7 variables, de 5 a 9 perfiles). Con prompt + esquema, un cambio es una edición de texto y se reevalúa en minutos |
| IA local (modelo abierto con llama-server, Ollama o vLLM) | Sin costo por llamada ni clave externa; los datos no salen del servidor | Desplegarla exige un servidor con GPU encendido todo el día (costo fijo aunque nadie use la app), o una CPU demasiado lenta para responder en el momento; peor comprensión de casos ambiguos o en otro idioma | Con la API, el servicio es un proceso Node pequeño sin GPU (Render, `render.yaml`), se paga solo por llamada y `TOPE_DIARIO` fija el gasto máximo. Con el tráfico de una demo, eso sale más barato que mantener una GPU. El servidor nunca registra el texto del caso en logs |
| RAG sobre documentos de las comunas | Respuestas con contexto local | El LLM terminaría citando cifras de comunas | Rompe la regla de que los números vienen solo del simulador |
| Agentes LLM dentro de la simulación | Comportamiento «humano» de hogares | 500 réplicas × 52 comunas × 10 años = 260 000 decisiones por escenario; no reproducible por semilla; sin datos para validarlo | El Monte Carlo con flujos calibrados (ADR-0002) es reproducible y se valida contra el censo |
| Solo palabras clave | Determinista, sin red | Falla con «casa matriz», «departamento de logística», negaciones | Se mantiene como respaldo: la app funciona sin el servidor |

## Consecuencias

- Cambiar el catálogo es editar `caso.ts` y correr `npm run evaluar`; no hay pipeline de entrenamiento.
- La interpretación no es reproducible bit a bit (el modelo puede variar), pero solo mueve pesos dentro del
  catálogo y la persona los confirma. El ranking y las bandas sí son reproducibles por semilla.
- La clave de Anthropic vive solo en `servidor-guia/`, con tope por IP y tope diario; si el servidor no
  responde, se usa la detección por palabras clave.
