# Taxonomía LVC y formas físicas, híbridas y modernas

Complementa a [`simulation-taxonomy.md`](./simulation-taxonomy.md). Ese documento cubre sobre todo la **simulación constructiva**, el enfoque matemático-computacional clásico de la Investigación de Operaciones. En ingeniería y ciencias aplicadas, la simulación abarca un espectro más amplio que se clasifica según **quién interactúa**, **qué parte es real** y **cómo se acopla al tiempo**.

La clasificación estándar en ingeniería de sistemas parte de la taxonomía **LVC (Live, Virtual, Constructive)** y hoy se extiende hacia paradigmas físicos, híbridos y de inteligencia artificial.

## 1. Taxonomía LVC (según quién opera y qué es real)

- **Simulación constructiva:** sistemas simulados operados por entidades simuladas, sin intervención humana en tiempo real. Aquí entran DES, ABM, Dinámica de Sistemas, Monte Carlo y simulación física numérica (elementos finitos/FEM, dinámica de fluidos/CFD). El reloj puede acelerarse o ralentizarse arbitrariamente.
- **Simulación virtual (*human-in-the-loop*, HITL):** personas reales operando sistemas simulados. El reloj es estrictamente **tiempo real (1:1)** porque debe responder a la percepción y los reflejos humanos. Ejemplos: simuladores de vuelo, entrenamiento quirúrgico en VR, videojuegos de simulación.
- **Simulación en vivo (*live*):** personas reales operando sistemas reales, pero en un escenario o entorno artificial controlado. Ejemplos: *Chaos Engineering* en servidores de producción, ejercicios de Red Team / Blue Team en ciberseguridad, simulacros de evacuación o maniobras con sensores láser.

## 2. Formas físicas, híbridas y modernas

Más allá de LVC, existen variantes donde el límite entre lo físico y lo digital se difumina:

- **Simulación física / analógica:** no depende de un motor de software, sino de leyes físicas replicadas a escala o en condiciones controladas. Ejemplos: túneles de viento para aerodinámica, maquetas hidráulicas de represas y pruebas de choque (*crash tests*) con maniquíes instrumentados.
- **Hardware-in-the-Loop (HIL) y Software-in-the-Loop (SIL):** híbrido crítico en sistemas embebidos, automotriz y aeroespacial. En **HIL**, un componente físico real (por ejemplo, la ECU de un motor o un microcontrolador) se conecta a un simulador que le inyecta señales eléctricas simuladas en tiempo real para probar cómo reacciona ante fallos extremos sin destruir el equipo real.
- **Gemelos digitales (*digital twins*):** a diferencia de la simulación tradicional (que corre *offline* con parámetros estimados), un gemelo digital está acoplado bidireccionalmente en tiempo real a un activo físico mediante telemetría/IoT. Recibe el estado real continuamente y permite probar escenarios *what-if* sobre el estado vivo del sistema.
- **Simulación generativa / *world models* (IA):** en lugar de programar ecuaciones diferenciales o reglas explícitas, redes neuronales (modelos de difusión, transformadores o *reinforcement learning*) aprenden la física y dinámica del entorno directamente a partir de datos. Se usa para entrenar robots, vehículos autónomos o simular comportamientos sociales complejos con enjambres de LLMs.

## Comparativa general

| Forma de simulación | Operador | Sistema | Reloj | Propósito principal |
|---------------------|----------|---------|-------|---------------------|
| Constructiva | Simulado | Simulado | Escalable (más rápido/lento que real) | Análisis estadístico, optimización, predicción |
| Virtual (HITL) | Real | Simulado | Tiempo real (1:1) | Entrenamiento humano, ergonomía, UX |
| En vivo (live) | Real | Real (entorno controlado) | Tiempo real (1:1) | Validación operativa, resiliencia, protocolos |
| HIL (híbrida) | Hardware real | Entorno simulado | Tiempo real estricto (duro) | Verificación de firmware y controladores embebidos |
| Física / analógica | Real / instrumentado | Físico a escala | Tiempo real / leyes físicas | Validar fenómenos complejos difíciles de modelar numéricamente |
| Gemelo digital | Real + automatizado | Físico + réplica digital | Sincronizado en vivo | Monitoreo predictivo, mantenimiento, control operativo |
| World models (IA) | Agentes / prompts | Aprendido por datos | Por pasos o *frames* | Entrenamiento de agentes autónomos, escenarios no formalizables |

## Simulación frente a emulación

En informática también suele trazarse una frontera precisa entre ambas:

- **Simulación:** replica el *comportamiento externo observable* de un sistema (enfoque de caja negra).
- **Emulación:** replica su *funcionamiento interno*, instrucción por instrucción (como un emulador de arquitectura de CPU o de consola).

## Relación con las skills del proyecto

Las skills del proyecto (`sim-scoping`, `des-montecarlo-builder`, `abm-ca-builder`, `llm-agents-sim`) trabajan en el cuadrante **constructivo**. Si el proyecto implica humanos en vivo (virtual), hardware o telemetría real (HIL, gemelo digital), el Paso 2 de `sim-scoping` lo marca en el eje de acoplamiento: el reloj pasa a tiempo real y el estado debe ser autoritativo en un solo lugar.
