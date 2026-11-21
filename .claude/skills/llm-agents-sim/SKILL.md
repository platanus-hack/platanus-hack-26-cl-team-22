---
name: llm-agents-sim
description: Construye simulaciones donde los agentes razonan con un LLM: motor autoritativo, acciones validadas, pasos síncronos concurrentes, memoria, presupuesto de llamadas y record/replay reproducible.
---

# llm-agents-sim

Última revisión: 2026-11-21. Plantillas verificadas con Python 3 (asyncio) usando un LLM simulado.

Complementa a `abm-ca-builder`: todo lo que dice sobre la spec, las métricas de emergencia y la validación con varias semillas sigue aplicando. Esta skill añade lo específico de los agentes con LLM.

## Paso 0: ¿hace falta un LLM?

Usa un LLM solo en las decisiones que requieren lenguaje o juicio abierto: negociar, persuadir, interpretar mensajes o improvisar ante situaciones nuevas. Lo rutinario (moverse, consumir, seguir una cola) va con reglas.

El diseño recomendado es híbrido: reglas por defecto y una llamada al LLM solo cuando se cumple un disparador (llega un mensaje, aparece un conflicto o pasan N pasos). Documenta en la spec qué decide el LLM y qué decide el código.

## Paso 1: arquitectura (principio central)

**El LLM propone; el motor dispone.** El LLM nunca modifica el estado. Devuelve una acción en JSON, el motor la valida contra un catálogo cerrado de acciones y solo entonces la aplica.

Ciclo de cada agente: percibir → recuperar memoria → decidir (LLM) → validar → actuar (motor).

```python
import json
ACTIONS = {"mover": {"dir"}, "esperar": set(), "hablar": {"a", "msg"}}   # catálogo cerrado

def validate(raw: str):
    try: a = json.loads(raw)
    except json.JSONDecodeError: return None
    if not isinstance(a, dict) or a.get("accion") not in ACTIONS: return None
    if set(a.get("args", {})) != ACTIONS[a["accion"]]: return None
    return a                                    # además, valida aquí reglas del mundo (rangos, permisos)
```

Ventaja para sistemas multijugador: un humano y un agente LLM usan exactamente la misma interfaz de acciones, así que pueden convivir en la misma simulación sin código especial.

## Paso 2: pasos síncronos y concurrentes

Todos los agentes deciden en paralelo sobre la misma foto del estado `t`. Después el motor resuelve los conflictos y aplica las acciones en un orden fijo (por id). Así se evita el sesgo de orden y se aprovecha la concurrencia.

```python
import asyncio
async def decide(gw, agent, obs, step, retries=1):
    prompt = (f"Eres {agent['nombre']}. {agent['persona']}\nObservas: {json.dumps(obs)}\n"
              f"Acciones: {list(ACTIONS)}. Responde SOLO JSON {{\"accion\":..,\"args\":{{..}}}}")
    for _ in range(retries + 1):
        raw = await gw.ask(prompt, salt=f"{agent['id']}|{step}")
        if (a := validate(raw)): return a, True
        prompt += f"\nTu respuesta anterior no era válida: {raw[:200]!r}. Responde SOLO el JSON."
    return {"accion": "esperar", "args": {}}, False      # acción por defecto; cuenta el fallo

async def step(gw, agents, state, t):
    snap = dict(state)                                       # todos ven el MISMO estado t
    results = await asyncio.gather(*[decide(gw, a, observe(snap, a), t) for a in agents])
    for a, (act, ok) in sorted(zip(agents, results), key=lambda r: r[0]["id"]):
        apply(state, a, act)                                 # el motor aplica y resuelve conflictos
```

El reintento debe incluir la respuesta inválida como retroalimentación. Repetir el mismo prompt tiende a repetir el mismo error.

## Paso 3: gateway con presupuesto, caché y record/replay

Toda llamada al LLM pasa por un único gateway, que hace cuatro cosas:

1. Limita la concurrencia con un semáforo.
2. Guarda cada respuesta en un log JSONL indexado por el hash de (agente, paso, prompt).
3. En modo replay, responde desde el log sin llamar a la API. Esto da reproducibilidad exacta, tests sin costo y demos que no fallan por la red.
4. Cuenta las llamadas.

```python
import hashlib, os
class LLMGateway:
    def __init__(self, call, log_path, mode="record", max_concurrency=8):
        self.call, self.mode, self.log_path = call, mode, log_path   # call: async (prompt) -> str
        self.sem, self.cache, self.calls = asyncio.Semaphore(max_concurrency), {}, 0
        if os.path.exists(log_path):
            for line in open(log_path):
                r = json.loads(line); self.cache[r["k"]] = r["out"]
    async def ask(self, prompt, salt=""):
        k = hashlib.sha256(f"{salt}|{prompt}".encode()).hexdigest()[:16]
        if k in self.cache: return self.cache[k]
        if self.mode == "replay": raise KeyError(f"respuesta no registrada: {k}")
        async with self.sem:
            out = await self.call(prompt); self.calls += 1
        self.cache[k] = out
        with open(self.log_path, "a") as f: f.write(json.dumps({"k": k, "out": out}) + "\n")
        return out
```

- `call` se inyecta, así el motor no depende de ningún proveedor. Usa la salida estructurada o tool use del proveedor si existe, y deja `validate` como segunda barrera.
- `temperature=0` no garantiza determinismo. La reproducibilidad la da el replay.
- Añade backoff exponencial ante errores 429 y un timeout por llamada; si se agota, usa la acción por defecto.

## Paso 4: presupuesto (calcularlo antes de ejecutar)

- Llamadas ≈ agentes × pasos × fracción de pasos con disparador × (1 + tasa de reintento).
- Costo ≈ llamadas × (tokens de entrada × precio de entrada + tokens de salida × precio de salida). Consulta los precios vigentes del proveedor; no los asumas.
- Tiempo por paso ≈ latencia de una llamada × ⌈agentes / concurrencia⌉.

Reglas para controlarlo:

- Usa un modelo económico para las decisiones rutinarias y uno premium solo para las críticas.
- Mantén las observaciones compactas: estado relevante en JSON, no descripciones largas.
- Pon un tope de llamadas por ejecución que detenga la simulación al alcanzarse.
- En una demo en vivo, precalienta el log y usa replay como respaldo.

## Paso 5: memoria

Inspirada en Generative Agents (Park et al., 2023), en versión ligera:

- **Corto plazo:** las últimas k observaciones.
- **Largo plazo:** una lista de recuerdos con importancia (1–10, asignada por el LLM o por reglas) y paso. Para cada prompt se recuperan los N recuerdos con mayor puntuación combinada de recencia, importancia y relevancia (la relevancia por embeddings es opcional).
- **Reflexión:** cada M pasos, el agente resume su memoria en 2–3 conclusiones, que se guardan como recuerdos de importancia alta.

La memoria también es estado: debe serializarse junto con el estado del mundo para que el replay funcione.

## Paso 6: validación (en `tests/`)

- **Motor con LLM simulado:** una política determinista más un ~10 % de respuestas basura. Comprueba que el motor no se rompe, que se aplica la acción por defecto y que la cuenta de inválidas es correcta. Referencia verificada: 20 agentes × 5 pasos con 10 % de basura → 0 inválidas tras un reintento con retroalimentación.
- **Replay:** record y luego replay deben dar la misma trayectoria con 0 llamadas.
- **Métricas de calidad del agente:** tasa de acciones válidas, diversidad de acciones, coherencia con la persona (revisada por muestreo).
- **Línea base:** compara las métricas de emergencia con una versión de reglas. Si el LLM no cambia nada medible, sobra.
- **Sensibilidad al prompt:** dos redacciones equivalentes del prompt no deberían cambiar la conclusión. Repórtalo.

## Checklist de entrega

- [ ] Spec: qué decide el LLM, qué decide el código y cuáles son los disparadores
- [ ] Catálogo cerrado de acciones con validación
- [ ] Pasos síncronos con foto del estado y orden fijo de aplicación
- [ ] Gateway con semáforo, log JSONL, modo replay y tope de llamadas
- [ ] Presupuesto calculado en el README
- [ ] Tests con LLM simulado y de replay
- [ ] Comparación con una línea base de reglas

## Errores comunes

- Dejar que el LLM escriba el estado o devuelva texto libre que se interpreta a mano.
- Llamar al LLM en cada paso y para cada agente sin disparadores.
- Ejecutar los agentes en serie, de modo que la latencia se multiplica por el número de agentes.
- Tratar `temperature=0` como si fuera reproducibilidad.
- Demos que dependen de la red sin replay de respaldo.
- Concluir "emergió X" sin compararlo con una línea base.
