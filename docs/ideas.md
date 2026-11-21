# Tablero de ideas

Usar en el kickoff: cada persona propone ideas, se filtran con la compuerta, se puntúan y se elige una. Tiempo sugerido: 45 minutos como máximo.

## 1. Compuerta (si falla una, la idea se descarta)

Basada en `docs/track-simulations.md`.

- [ ] **Pregunta "¿qué pasaría si…?"**: alguien aprende algo al correrla; no es solo una animación.
- [ ] **No es Multiplayer**: no es un juego donde personas juegan entre sí.
- [ ] **No es Physical World**: no lee datos reales para comandar algo en vivo.
- [ ] **No es solo una fórmula o planilla**: hay dinámica, azar o interacción que una planilla no resuelve.
- [ ] **Hay modelo detrás**: no es solo una visualización.
- [ ] **Cabe en 36 h**: un modelo mínimo corre headless en las primeras horas (ver `docs/work-plan.md`).

## 2. Puntuación (0 a 5 por criterio)

Los pesos son los de `docs/evaluation-rubric.md`. Puntaje = suma de (nota × peso) / 5, sobre 100.

| Criterio | Peso | Pregunta guía |
|----------|------|---------------|
| Originalidad | 15 | ¿Sorprende, o es la primera idea que se le ocurre a cualquiera? |
| Ambición | 20 | ¿Apunta alto para 36 h sin volverse inalcanzable? |
| Ejecución | 20 | ¿Podemos dejarlo pulido, con flujos que funcionan y una demo ensayable? |
| Aspecto técnico | 25 | ¿Hay ingeniería real: kernel propio, validación, réplicas, agentes? |
| Impacto | 20 | ¿Quién usaría el resultado y qué decisión cambia? |

## 3. Criterios de desempate

1. ¿Podemos mostrar un resultado que **sorprenda al propio equipo**?
2. ¿Qué paradigma encaja (`sim-scoping`, Paso 3) y tenemos ya la base en `core/`?
3. ¿El riesgo principal se puede probar en las primeras 2 horas?
4. ¿La demo funciona sin red (grabación o replay si usa LLM)?

## 4. Plantilla por idea

Copiar este bloque en la sección "Ideas" para cada propuesta.

```markdown
### <Nombre corto>
- **Propone:** <persona>
- **Pregunta "¿qué pasaría si…?":**
- **Quién la usaría y qué decisión cambia:**
- **Paradigma (DES / Monte Carlo / ABM / CA / mixto):**
- **Parámetros que se variarían:**
- **Métricas de salida:**
- **Resultado que podría sorprender:**
- **Riesgo principal y cómo probarlo en 2 h:**
- **Compuerta:** ✅ / ❌ (cuál falla)
- **Notas (O / A / E / T / I, 0 a 5):** _ / _ / _ / _ / _
- **Puntaje (/100):**
```

## 5. Decisión

Elegida: _
Motivo en una línea: _

Siguiente paso: completar `docs/sim-spec.md` con `sim-scoping` y repartir roles según `docs/work-plan.md`.

## Ideas

<!-- Agregar aquí, una sección por idea. -->

### Simulador realista de viajes: costos vs. fricción (idea lateral, Santiago piloto)
- **Estado:** idea lateral; guardada como referencia, sin puntuar ni decidir.
- **Pregunta "¿qué pasaría si…?":** ¿cuánto ahorra y cuánta fricción asume un viajero según las opciones que elige (eSIM global vs. chip local, transfer vs. bus, tarjeta vs. casa de cambio)?
- **Problema:** los planificadores recomiendan por afiliados y usan promedios desactualizados. Ejemplo: 1 GB a ~US$4 con eSIM global frente a ~100 GB por ~US$10 con un chip prepago local (WOM).
- **Quién la usaría y qué decisión cambia:** viajeros que planifican un viaje; decide qué contratar en conectividad, transporte, escapadas, comida y pagos.
- **Rubros del MVP:** conectividad, transporte (aeropuerto y urbano), escapadas (Viña del Mar / Valparaíso), comida por tiers, divisas y pagos.
- **Entradas:** días de viaje, perfil (ej. turista extranjero sin RUT), consumo de datos, escapadas deseadas, tolerancia a la fricción.
- **Salida:** 3 escenarios en paralelo (Cero fricción / Balanceado / Optimizado local) con ahorro en USD y CLP frente a un `friction_score` y el tiempo extra.
- **Premisas de diseño:**
  - Dataset pre-indexado y actualizado por lotes (`last_verified_at`); sin scraping en tiempo real.
  - Motor 100 % determinista; un LLM solo como capa opcional para traducir lenguaje natural a parámetros JSON.
  - Esquema agnóstico a la ciudad; Santiago es solo el seed.
  - Capas Domain / Application / Infrastructure; primero motor y dataset, después la UI.
- **Pendiente de definir (preguntas abiertas del planteamiento):** fórmula exacta del `friction_score`, fuentes y frecuencia de actualización del dataset, formato de almacenamiento (JSON, SQLite o PostgreSQL).
- **Riesgo con la compuerta del track:** el motor determinista es, en el fondo, una proyección que sale de reglas y fórmulas. Una de las exclusiones de `track-simulations.md` es "una proyección que sale de una fórmula o de una planilla". Para calificar necesitaría un modelo con dinámica o incertidumbre (por ejemplo, variabilidad de precios, filas, retrasos, agentes viajeros) que dé resultados no obvios.
- **Compuerta:** sin evaluar. Probable ❌ en "no es solo una fórmula o planilla" si queda como está.
