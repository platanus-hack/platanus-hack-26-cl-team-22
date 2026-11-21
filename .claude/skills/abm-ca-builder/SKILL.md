---
name: abm-ca-builder
description: Construye modelos basados en agentes (ABM) y autómatas celulares con spec ODD, activación y vecindad explícitas, Mesa 3 o NumPy/TS, métricas de emergencia y validación multi-semilla.
---

# abm-ca-builder

Última revisión: 2026-11-21. Plantillas verificadas con Mesa 3.5.2 y NumPy 2.5.

**Requisito:** una spec con la pregunta y las métricas. Si no existe, aplica primero `sim-scoping`.

**Estructura del repo:** la misma que en `des-montecarlo-builder` (`core/`, `experiments/`, `viz/`, `tests/`, `docs/sim-spec.md`).

## Paso 1: spec ODD-lite (en `docs/sim-spec.md`)

Basada en el protocolo ODD (Overview, Design concepts, Details), el estándar para describir ABM:

- **Propósito:** la pregunta que responde.
- **Entidades y variables de estado:** agentes, celdas, entorno.
- **Escalas:** qué representa una celda y qué representa un paso de tiempo.
- **Proceso y orden de activación:** qué hace cada agente en cada paso y en qué orden (Paso 2).
- **Conceptos de diseño:** qué emerge, qué percibe cada agente, dónde entra el azar.
- **Inicialización:** distribución inicial y semilla.
- **Entradas:** parámetros, con rango.

## Paso 2: decisiones que cambian los resultados (documéntalas todas)

**Activación:**

- **Síncrona:** todos leen el estado `t` y escriben `t+1`, con doble buffer. Es la norma en CA clásicos.
- **Asíncrona aleatoria:** se baraja el orden en cada paso. Es la norma en ABM sociales.
- **Secuencial fija:** introduce sesgo. Evítala.

**Vecindad:** Moore (8 vecinos), von Neumann (4), radio r o red.

**Fronteras:** toroidal, bordes fijos o reflectantes.

**Conflictos:** si dos agentes quieren la misma celda, define una regla explícita (orden aleatorio, prioridad, sorteo).

## Paso 3: implementación según el stack

**Mesa 3** (Python, análisis y prototipo rápido). Comprueba la versión instalada: la API cambió en la 3.0 (los schedulers fueron reemplazados por `AgentSet`).

```python
import mesa

class Persona(mesa.Agent):
    def step(self):
        ...  # percibir → decidir → actuar; usar self.random o self.model.rng, nunca random global

class Modelo(mesa.Model):
    def __init__(self, n=100, rng=42):
        super().__init__(rng=rng)
        Persona.create_agents(self, n)
        self.datacollector = mesa.DataCollector(model_reporters={"metrica": lambda m: ...})
    def step(self):
        self.agents.shuffle_do("step")          # activación asíncrona aleatoria
        self.datacollector.collect(self)
```

**NumPy puro** (CA y ABM en rejilla con reglas vectorizables). Mucho más rápido. Ejemplo de CA síncrono y toroidal:

```python
import numpy as np
def life_step(g):                              # g: arreglo uint8 0/1
    n = sum(np.roll(np.roll(g, i, 0), j, 1)
            for i in (-1, 0, 1) for j in (-1, 0, 1) if (i, j) != (0, 0))
    return ((n == 3) | ((g == 1) & (n == 2))).astype(np.uint8)   # devuelve un buffer nuevo
```

**TypeScript/Canvas** (demo en vivo). Usa arreglos tipados (`Uint8Array`) con doble buffer y un PRNG con semilla (`mulberry32`, el de `des-montecarlo-builder`). Desacopla la simulación del render: ejecuta N pasos de simulación por frame y dibuja solo el estado.

**Rendimiento:**

- En espacio continuo, usa un hash espacial (celdas del tamaño del radio de percepción) para evitar comparar todos contra todos (O(n²)).
- Vectoriza las reglas homogéneas.
- Perfila antes de optimizar.

## Paso 4: métricas de emergencia

Sin una métrica numérica solo tienes una animación, no un resultado. Define métricas agregadas (índice de segregación, tamaño del cluster mayor, densidad, entropía, polarización), recógelas en cada paso y guárdalas en CSV.

## Paso 5: validación (en `tests/`)

- **Reglas locales:** tests unitarios de una regla en un caso pequeño. Ejemplos: un glider se desplaza (1,1) en 4 pasos; un agente insatisfecho se mueve y uno satisfecho no.
- **Reproducibilidad:** misma semilla, misma trayectoria exacta.
- **Orientada a patrones:** el modelo debe reproducir al menos 2 patrones conocidos del sistema real o del caso clásico.
- **Múltiples semillas:** reporta las métricas con intervalo de confianza sobre al menos 10 semillas. Una emergencia que aparece en 1 de 10 semillas no es un resultado.
- **Sensibilidad:** barrido del parámetro clave, graficando la métrica contra el parámetro. Busca y documenta transiciones de fase.

Referencia verificada (Schelling, NumPy): rejilla 40×40 toroidal, densidad 0.9, tolerancia 0.4, activación asíncrona aleatoria → índice de segregación 0.50 → 0.83 en 30 pasos.

## Checklist de entrega

- [ ] Spec ODD-lite
- [ ] Activación, vecindad, fronteras y conflictos documentados
- [ ] Azar solo desde RNG con semilla del modelo
- [ ] CA síncrono con doble buffer (nunca actualizar en el mismo arreglo)
- [ ] Métricas de emergencia en CSV
- [ ] Tests de reglas locales y de reproducibilidad
- [ ] Resultados multi-semilla con intervalos y un barrido de sensibilidad
- [ ] Render separado del núcleo

## Errores comunes

- Actualizar las celdas en el mismo arreglo que se está leyendo (contamina la actualización síncrona).
- Iterar los agentes siempre en el mismo orden.
- Usar `random` global en lugar del RNG del modelo.
- Concluir a partir de una sola semilla.
- Que la regla del agente dependa del frame rate de la visualización.
