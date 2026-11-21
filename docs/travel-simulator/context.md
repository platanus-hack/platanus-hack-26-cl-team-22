# Simulador realista de viajes (costos vs. fricción): contexto

> Idea lateral. Este documento es la base de hechos; los entregables de planificación viven en los demás archivos de esta carpeta.

## Problema

Los planificadores de viaje fallan por sesgo de afiliados (recomiendan opciones caras, como eSIMs globales o tours) y por promedios estáticos desactualizados. Ejemplo: 1 GB a ~US$4 con una eSIM internacional frente a ~100 GB por ~US$10 con un chip prepago local (WOM).

## Premisas arquitectónicas (obligatorias)

- **Dataset pre-indexado, sin scraping en tiempo real.** Base local normalizada, actualizada por lotes con `last_verified_at`.
- **Motor determinista.** Cálculo de costos, filtrado y escenarios con reglas y matemáticas. Un LLM solo como capa opcional para traducir lenguaje natural a parámetros JSON.
- **Esquema agnóstico a la ciudad.** Santiago de Chile es solo el seed.
- **Capas** Domain / Application / Infrastructure; primero motor y dataset, después la UI.

## Alcance del MVP (Santiago)

1. Conectividad: eSIMs globales frente a planes prepago locales (WOM, Entel, Movistar, Claro).
2. Transporte: aeropuerto (Centropuerto/Turbus frente a Uber/transfer) y movilidad urbana (Metro/Red bip! frente a apps).
3. Escapadas: Viña del Mar / Valparaíso (bus desde terminal frente a tour).
4. Comida: tiers (menú del día/local, casual, turístico).
5. Divisas y pagos: tarjeta internacional (spread/comisión) frente a casas de cambio.

## Mecánica de simulación

- **Entradas:** días de viaje, perfil (ej. turista extranjero sin RUT), consumo de datos, escapadas deseadas, tolerancia a la fricción y perfil del dispositivo.
- **Filtros duros:** descartar opciones incompatibles (requiere RUT, tipo de SIM no soportado por el teléfono).
- **Normalización:** costo real por día y costo efectivo por GB según la duración.
- **Salida:** 3 escenarios en paralelo (Cero fricción / Balanceado / Optimizado local) con ahorro en USD y CLP frente al `friction_score` y el tiempo extra.

## Ángulo añadido: auditar asistentes de IA

Dar el mismo perfil de viaje a varios asistentes de IA (Claude, ChatGPT, Gemini…), extraer lo que recomiendan y pasarlo por el motor determinista para medir cuánto sobrepagaría y cuánta fricción asumiría un viajero que siga cada consejo.

- El motor de costos sigue siendo determinista; las IAs son lo que se mide, no lo que calcula.
- Aporta agentes con respuestas variables (réplicas, intervalos de confianza) y una pregunta no trivial: ¿cuánto sesgo tienen las IAs hacia opciones caras o de afiliados?
- Con record/replay (`core/llm_gateway.py`) la demo no depende de la red.
- Ataca el riesgo de la compuerta del track: sin esto sería una proyección que sale de reglas y fórmulas.

## Restricción clave: tipo de SIM y dispositivo

Verificado el 2026-11-21. Las fuentes son guías de terceros y la web de WOM, y discrepan entre sí, por lo que cada dato del dataset necesita `last_verified_at`.

- **WOM** vende eSIM prepago (Plan Zero): se compra en su web, envía un QR por correo y no cobra activación. Exige validación de identidad, que acepta pasaporte extranjero. No se confirmó si esa validación aplica igual a la eSIM prepago. Fuentes: [WOM, cómo activo la eSIM](https://www.wom.cl/centro-de-ayuda/como-activo-la-esim/), [WOM, activar chip prepago](https://www.wom.cl/centro-de-ayuda/como-activar-mi-chip-prepago/).
- **Entel, Movistar y Claro:** la eSIM suele ir atada a un plan o a una línea existente; para un turista el camino habitual es el chip físico. Fuente: [SimOptions](https://www.simoptions.com/esim-providers-in-chile/).
- **Chip físico:** algunas tiendas de Entel rechazan vender a turistas y a veces hay que probar varias tiendas para registrar la SIM. Fuente: [Traveltomtom](https://www.traveltomtom.net/destinations/south-america/chile/sim-card-chile).
- **eSIM de viaje** (Holafly, Airalo, Roafly): se compran antes del viaje y evitan las reglas de ID e IMEI de Chile.

Consecuencia para el modelo: el perfil del dispositivo (`has_physical_sim_slot`, `supports_esim`) y el `sim_type` de cada opción son un **filtro duro**. Un teléfono solo eSIM no puede usar un chip prepago físico, y entonces cambia el "óptimo local".

## Preguntas abiertas

- Fórmula exacta del `friction_score`.
- Fuentes y frecuencia de actualización del dataset.
- Formato de almacenamiento (JSON, SQLite o PostgreSQL).
- Qué asistentes de IA y qué prompts se usarán en la auditoría.
