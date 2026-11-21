# Taxonomía de simulación: los 5 ejes

En la teoría formal de Modelado y Simulación (M&S, fundamentada en autores como Law, Banks y Zeigler), los tipos de simulación no son una lista suelta de categorías, sino **combinaciones sobre 5 ejes de clasificación ortogonales**.

Cualquier simulación que exista, desde un túnel de viento hasta un motor de física o un *world model* de IA, se define eligiendo una posición en cada uno de estos ejes.

## 1. Eje del Tiempo (¿El tiempo altera el estado?)

- **Estática:** el tiempo no es una variable del modelo; representa el sistema en un instante fijo o evalúa un espacio de probabilidades (ej. simulación de Monte Carlo para calcular integrales o riesgo financiero).
- **Dinámica:** el estado del sistema evoluciona a lo largo del tiempo (ej. propagación de un virus, tráfico de red, dinámica orbital).

## 2. Eje del Cambio de Estado (¿Cómo cambia el sistema?)

- **Continua:** las variables de estado cambian de forma fluida en cada instante. Se modela con ecuaciones diferenciales ordinarias o parciales (ODEs/PDEs) y se resuelve por integración numérica (Δt).
- **Discreta:** el estado solo cambia en puntos contables y específicos del tiempo llamados **eventos** (ej. llega un paquete a un router, falla un servidor).
- **Híbrida (combinada):** mezcla variables continuas que disparan eventos discretos al cruzar un umbral (ej. un tanque que se llena continuamente hasta que un sensor discreto cierra la válvula).

## 3. Eje de la Incertidumbre (¿Hay aleatoriedad?)

- **Determinista:** no contiene variables aleatorias. Dado el mismo estado inicial y las mismas entradas, siempre produce exactamente la misma salida (ej. circuitos lógicos ideales o mecánica orbital clásica).
- **Estocástica:** incorpora al menos una variable aleatoria gobernada por una distribución de probabilidad. Sus salidas son estimaciones estadísticas que requieren múltiples réplicas para ser válidas.

## 4. Eje de la Naturaleza / Acoplamiento (¿Qué es real y qué es simulado?)

- **Física / analógica:** usa materia real a escala o sistemas físicos análogos (túneles de viento, circuitos eléctricos que imitan sistemas mecánicos).
- **Constructiva (digital pura):** todo es software (operador y entorno simulados).
- **Virtual (*human-in-the-loop*):** un humano real opera un entorno digital en tiempo real.
- **En vivo (*live*):** humanos y equipos reales operan en un escenario artificial controlado.
- **Híbrida de ingeniería (HIL / SIL / gemelo digital):** conecta hardware físico real o telemetría en vivo directamente al motor de simulación.

## 5. Eje del Paradigma de Representación (¿De dónde salen las reglas?)

- **Basada en ecuaciones (top-down):** se programan leyes matemáticas globales o flujos agregados (Dinámica de Sistemas, Elementos Finitos/FEM, Fluidos/CFD).
- **Basada en procesos / eventos (DES):** se modela el flujo de entidades a través de colas, recursos y estaciones de servicio.
- **Basada en agentes (bottom-up / ABM):** se programan reglas locales en entidades autónomas; el comportamiento global del sistema *emerge* de sus interacciones.
- **Basada en datos / generativa (IA):** no se escriben ecuaciones ni reglas explícitas; un modelo neuronal aprende la función de transición de estado `S(t+1) = f(S(t), A(t))` a partir de datos empíricos.

## Cómo se combinan en la práctica

Para clasificar cualquier simulación con rigor técnico, basta con cruzar sus coordenadas en los 5 ejes:

| Ejemplo real | Tiempo | Estado | Incertidumbre | Acoplamiento | Representación |
|--------------|--------|--------|---------------|--------------|----------------|
| Simulador de vuelo comercial | Dinámica | Continua | Estocástica (clima) | Virtual (HITL) | Ecuaciones físicas |
| Simulación de red / colas de servidores | Dinámica | Discreta | Estocástica | Constructiva | Eventos discretos (DES) |
| Prueba de ECU automotriz | Dinámica | Híbrida | Determinista / fallos | HIL (hardware real) | Ecuaciones + lógica |
| Estimación de riesgo financiero | Estática | Discreta | Estocástica | Constructiva | Monte Carlo |
| Entrenamiento de robot en *world model* | Dinámica | Discreta (frames) | Estocástica | Constructiva / Virtual | Basada en datos (IA) |

Esta matriz es la base estándar: si necesitas diseñar o evaluar una simulación, definir primero sus 5 ejes te dicta qué arquitectura de software, qué tipo de reloj y qué método de validación necesitas implementar.

## Ver también

- [`simulation-lvc-taxonomy.md`](./simulation-lvc-taxonomy.md): taxonomía LVC (constructiva, virtual, en vivo) y formas físicas, HIL, gemelos digitales y world models.

## Relación con las skills del proyecto

- `sim-scoping` usa estos ejes (Paso 2) para elegir paradigma y stack.
- `des-montecarlo-builder`, `abm-ca-builder` y `llm-agents-sim` cubren los paradigmas DES/Monte Carlo, ABM/CA y agentes con LLM.
- Fuera de su alcance: simulación continua basada en ecuaciones (ODEs/PDEs, dinámica de sistemas, FEM/CFD) y modelos basados en datos (world models).
