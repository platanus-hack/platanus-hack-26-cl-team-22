---
name: sim-scoping
description: Convierte una idea en especificación de simulación (5 ejes, paradigma DES/Monte Carlo/ABM/CA, stack, métricas, plan). Úsala antes de construir cualquier simulación o al oír 'quiero simular X'.
---

# sim-scoping: de idea a especificación de simulación

Última revisión: 2026-11-21

Usa esta skill antes de escribir código de simulación. Produce `docs/sim-spec.md`, decide el paradigma y el stack, y después entrega el trabajo a `des-montecarlo-builder` o a `abm-ca-builder`.

## Paso 1: fijar la pregunta

Una simulación responde una pregunta concreta; "modelar un sistema" no es una pregunta. Si el usuario no la dio, hazle estas preguntas todas juntas (máximo 5):

1. ¿Qué decisión o pregunta debe responder? Ejemplo: "¿cuántas cajas abrir para que la espera media baje de 5 min?"
2. ¿Qué entidades existen y qué hace cada una?
3. ¿Qué parámetros quiere variar?
4. ¿Qué métricas de salida importan, y en qué unidades?
5. ¿Habrá personas interactuando en vivo con la simulación?

Si falta algo que no es crítico, asume un valor y anótalo en la sección "Supuestos" de la spec.

## Paso 2: clasificar en los 5 ejes

| Eje | Pregunta | Consecuencia en el código |
|-----|----------|---------------------------|
| Tiempo | ¿El estado evoluciona? | Si no evoluciona: Monte Carlo, sin reloj |
| Cambio de estado | ¿Cambia de forma fluida o por eventos? | Por eventos: heap de eventos. Por pasos: bucle `step()` |
| Incertidumbre | ¿Hay azar? | Si lo hay, semillas, réplicas e intervalos de confianza son obligatorios |
| Acoplamiento | ¿Hay humanos o hardware en vivo? | Si los hay, reloj atado al tiempo real y estado autoritativo en un solo lugar |
| Representación | ¿De dónde salen las reglas? | Define el paradigma (Paso 3) |

Los ejes están correlacionados (DES implica estado discreto; humanos en vivo implican tiempo real). No fuerces combinaciones incoherentes.

## Paso 3: elegir paradigma (aplica la primera regla que coincida)

1. No hay dinámica temporal; solo hay que estimar una probabilidad, un valor esperado o un riesgo → **Monte Carlo**.
2. Entidades pasivas fluyen por recursos de capacidad limitada (colas, servidores, estaciones) → **DES**.
3. Entidades con decisiones propias interactúan entre sí y el resultado global emerge → **ABM**.
4. Espacio en rejilla donde todas las celdas siguen la misma regla local → **autómata celular (CA)**.
5. Mezcla (por ejemplo, clientes con reglas de decisión dentro de una cola) → DES como esqueleto y entidades con lógica propia. Documenta cuál de los dos controla el reloj.
6. Física continua o reglas que solo pueden aprenderse de datos → fuera del alcance de estas skills. Dilo explícitamente.

Prueba rápida entre DES y ABM: si al quitarle la "inteligencia" a las entidades el modelo sigue teniendo sentido, es DES.

## Paso 4: elegir stack

| Situación | Stack |
|-----------|-------|
| Análisis por lotes: réplicas, intervalos de confianza, barridos de parámetros | Python + NumPy/SciPy. DES: kernel propio o SimPy. ABM: Mesa 3 o NumPy |
| Demo visual en navegador, menos de ~10k entidades, sin backend | TypeScript + Canvas, PRNG con semilla, simulación en un Web Worker |
| Visualización en vivo con varios usuarios ajustando parámetros | Motor autoritativo en servidor (Python FastAPI + WebSocket, o Node). El cliente solo renderiza y envía comandos |
| CA grande (más de ~1M celdas) | NumPy vectorizado; en navegador, WebGL o shaders |
| Monte Carlo pesado | NumPy vectorizado; Numba si quedan bucles que no se pueden vectorizar |

**Regla del núcleo:** el modelo vive en `core/` sin dependencias de UI. La visualización lee el estado y nunca lo modifica. Así la misma lógica corre miles de réplicas headless y también la demo.

**Kernel propio o librería:** si la simulación es el corazón técnico del proyecto (por ejemplo, en un hackatón donde un agente revisa el repo), un kernel propio de ~40 líneas con tests demuestra comprensión y no es un simple wrapper. Si la simulación es solo un medio, usa la librería.

## Paso 5: escribir `docs/sim-spec.md`

```markdown
# Spec de simulación: <nombre>
## Pregunta que responde
## Clasificación (5 ejes)  ← tabla del Paso 2
## Paradigma y justificación
## Entidades y variables de estado
## Eventos (DES) o reglas locales (ABM/CA)
## Parámetros de entrada  (nombre, unidad, valor base, rango a explorar)
## Métricas de salida     (nombre, unidad, tipo: por observación / ponderada en tiempo / agregada)
## Validación             (caso teórico, patrones esperados, casos extremos)
## Experimentos           (réplicas, escenarios, barridos)
## Supuestos y simplificaciones
## Stack y estructura del repo
```

## Paso 6: plan de 36 horas (solo si es hackatón)

| Horas | Bloque | Entregable verificable |
|-------|--------|------------------------|
| 0–6 | Spec y modelo mínimo headless | `core/` ejecuta una réplica e imprime métricas |
| 6–10 | Validación | Tests contra un caso teórico y de reproducibilidad, en verde |
| 10–16 | Experimentos | Réplicas, intervalos de confianza y barrido de 1–2 parámetros en CSV |
| 16–28 | Visualización e interacción | Demo en vivo que lee el núcleo |
| 28–34 | README y resultados | Spec, cómo ejecutar, hallazgos con números |
| 34–36 | Margen | — |

No empieces la UI hasta que el núcleo pase sus tests.

## Anti-patrones

- Modelar todo "por si acaso": cada entidad debe estar ligada a una métrica de salida.
- Presentar una sola ejecución estocástica como resultado.
- Meter la lógica del modelo dentro del bucle de render (`requestAnimationFrame`, callbacks de UI).
- Usar `Math.random()` o `random.random()` globales: impiden reproducir resultados.
- Elegir ABM porque "se ve más impresionante" cuando el sistema es una cola.
