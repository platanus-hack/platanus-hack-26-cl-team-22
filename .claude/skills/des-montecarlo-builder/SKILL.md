---
name: des-montecarlo-builder
description: Construye simulaciones de eventos discretos (colas, recursos) y Monte Carlo con kernel validado, semillas, réplicas, intervalos de confianza y tests contra M/M/1 y Little.
---

# des-montecarlo-builder

Última revisión: 2026-11-21. Plantillas verificadas con Python 3, NumPy 2.5 y SciPy 1.18.

**Requisito:** una spec con la pregunta, las métricas y los parámetros. Si no existe, aplica primero `sim-scoping` o pide esos tres datos.

## Estructura del repo

```text
core/          modelo puro: kernel, entidades, eventos (sin I/O ni UI)
experiments/   réplicas, escenarios y barridos → results/*.csv
viz/           renderizado; lee estado, nunca lo modifica
tests/         validación teórica y reproducibilidad
docs/sim-spec.md
README.md      pregunta, cómo ejecutar, resultados con intervalos de confianza
```

## Paso 1: tabla de eventos (antes del código)

En la spec, para cada tipo de evento: qué variables de estado cambia y qué eventos futuros agenda.

| Evento  | Cambios de estado                                                   | Agenda                                          |
|---------|---------------------------------------------------------------------|-------------------------------------------------|
| llegada | si el servidor está libre lo ocupa; si no, encola                   | su servicio (si entró) y la siguiente llegada   |
| salida  | si hay cola, atiende al siguiente; si no, libera el servidor        | el siguiente servicio (si hay cola)             |

## Paso 2: kernel

```python
import heapq, itertools
import numpy as np

class Sim:
    def __init__(self, seed):
        self.t = 0.0
        self._q = []
        self._seq = itertools.count()          # desempate estable para eventos simultáneos
        self._ss = np.random.SeedSequence(seed)
    def rng(self):                              # un stream independiente por componente
        return np.random.default_rng(self._ss.spawn(1)[0])
    def schedule(self, delay, fn, *args):
        heapq.heappush(self._q, (self.t + delay, next(self._seq), fn, args))
    def run(self, until):
        while self._q and self._q[0][0] <= until:
            self.t, _, fn, args = heapq.heappop(self._q)
            fn(*args)
        self.t = until
```

Reglas:

- El reloj salta al siguiente evento; nunca avanza en pasos fijos.
- Pide un `sim.rng()` por fuente de azar (llegadas, servicio, etc.), en el mismo orden siempre. Esto habilita los números aleatorios comunes (CRN) al comparar escenarios.
- Nunca compares tiempos flotantes con `==`.
- Con SimPy: `simpy.Resource` para servidores y `env.process` para entidades. La regla de un generador por componente se mantiene.
- En navegador (TypeScript): heap binario propio y PRNG con semilla, nunca `Math.random()`:

```ts
export function mulberry32(a: number) {
  return () => { a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
export const expo = (u: () => number, rate: number) => -Math.log(1 - u()) / rate;
```

## Paso 3: estadísticas

Hay dos tipos, y confundirlos es el error más común:

- **Por observación (tally):** una muestra por entidad (tiempo de espera). Media simple.
- **Ponderada en el tiempo:** variables que persisten (largo de cola, utilización). Promediar por evento es incorrecto.

```python
class TimeWeighted:
    def __init__(self, t0=0.0, v0=0.0):
        self.t0, self.t, self.v, self.area = t0, t0, v0, 0.0
    def update(self, t, v):                     # llamar DESPUÉS de cambiar el estado, con el valor nuevo
        self.area += self.v * (t - self.t); self.t, self.v = t, v
    def mean(self, t_end):
        return (self.area + self.v * (t_end - self.t)) / (t_end - self.t0)
```

**Calentamiento (warm-up):**

- **Simulación terminante** (el sistema tiene un fin natural, como un día de banco): no hay warm-up; cada réplica es el período completo.
- **Estado estable** (el sistema arranca vacío y se estudia su régimen): agenda un evento `reset_stats` en `t = warmup` que vacíe las muestras y cree un `TimeWeighted(sim.t, estado_actual)`. Para elegir `warmup`, grafica la media móvil de la métrica en varias réplicas (método de Welch) y corta donde se estabiliza.

## Paso 4: réplicas e intervalos de confianza

```python
from scipy import stats
def ci(x, conf=0.95):
    x = np.asarray(x); m = x.mean()
    h = stats.t.ppf((1 + conf) / 2, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return m, h                                  # reportar como m ± h
```

- Usa una semilla distinta por réplica (`seed = i`). Empieza con 10 réplicas y calcula `s`. Para un semiancho objetivo ε, el número de réplicas es n ≈ (t·s/ε)².
- Para comparar escenarios A y B, usa la misma semilla en la réplica i de ambos (CRN) y calcula el intervalo sobre las diferencias pareadas A_i − B_i. Si no contiene 0, la diferencia es significativa.

## Paso 5: validación (obligatoria, en `tests/`)

- **Caso analítico:** configura el modelo como M/M/1, con ρ = λ/μ < 1. Valores teóricos: L = ρ/(1−ρ) y Wq = ρ/(μ−λ). El intervalo de confianza debe cubrir el valor teórico. Referencia verificada: λ=0.8, μ=1, 20 réplicas, T=20000, warm-up 1000 → Wq = 3.94 ± 0.19 (teórico 4.0), L = 3.95 ± 0.16 (teórico 4.0).
- **Ley de Little:** L ≈ λ·(Wq + 1/μ).
- **Reproducibilidad:** `run(seed=7) == run(seed=7)`, idéntico.
- **Casos extremos:** con λ → 0 no hay colas. Con ρ ≥ 1 la cola crece sin límite; el código debe detectarlo y advertir en lugar de reportar una media.

## Monte Carlo (sin reloj)

```python
def mc(f, n, seed, antithetic=True):
    u = np.random.default_rng(seed).random(n // 2 if antithetic else n)
    y = (f(u) + f(1 - u)) / 2 if antithetic else f(u)
    return y.mean(), 1.96 * y.std(ddof=1) / np.sqrt(len(y))
```

- Vectoriza siempre: genera todas las muestras como arreglos, sin bucles de Python.
- Elige n por precisión, no por intuición: n ≈ (1.96·s/ε)².
- Reducción de varianza: las variables antitéticas solo ayudan si `f` es monótona (verificado con e^u: semiancho 5.5 veces menor con el mismo n). Otras opciones: CRN al comparar escenarios y variables de control cuando hay una variable correlacionada de media conocida.
- Entrega siempre el intervalo de confianza y una gráfica de convergencia (estimación frente a n).

## Checklist de entrega

- [ ] Tabla de eventos en la spec
- [ ] `core/` sin imports de UI
- [ ] Un RNG con semilla por componente; nada de azar global
- [ ] Estadísticas ponderadas en el tiempo donde corresponde
- [ ] Warm-up justificado, o simulación declarada terminante
- [ ] Resultados como media ± semiancho con n réplicas
- [ ] Tests: caso analítico, Little, reproducibilidad, ρ ≥ 1
- [ ] README con la pregunta, el comando para reproducir y los resultados

## Errores comunes

- Reportar una sola ejecución.
- Promediar el largo de cola por evento en lugar de ponderarlo por tiempo.
- Compartir un único RNG entre llegadas y servicios (rompe CRN).
- Incluir el transitorio inicial en un estudio de estado estable.
- Avanzar el reloj con `dt` fijo en un modelo de eventos.
