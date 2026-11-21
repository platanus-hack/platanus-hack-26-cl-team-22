# ADR-0005: El motor simula las 52 comunas; la interfaz destaca 5 con estación

- **Estado**: Aceptado
- **Fecha**: 2026-11-21

## Contexto

Las interacciones (aire por la cuenca, mudanzas, vecindad en seguridad) necesitan todas las
comunas de la Región Metropolitana. Pero solo ~10 tienen estación de medición: en el resto, el
nivel de partida es estimado, y no se debe usar como prueba en la demo.

## Decisión

El motor simula las 52 comunas. La interfaz destaca las 5 de `comunas_destacadas`, elegidas
con la regla fija de `docs/modelo-aire.md`: las dos de mayor y las dos de menor nivel medido,
más las de la Zona B con estación.

| Comuna | Zona del plan | Nivel base |
|---|---|---|
| El Bosque | A | medido |
| Cerro Navia | A | medido |
| Puente Alto | A | medido |
| Las Condes | A | medido |
| Talagante | B | medido |

## Alternativas consideradas

| Opción | Pros | Contras | Por qué se descartó |
|---|---|---|---|
| Elegir comunas a mano | Más conocidas para el público | Parece elegido para el resultado | La regla fija evita esa sospecha |
| Simular solo las destacadas | Más rápido | Rompe las interacciones | Las comunas tienen que afectarse entre sí |

## Consecuencias

- Talagante es la única comuna de la Zona B destacada; sostiene los pasos 3 y 4 de la demo
  (ADR-0001).
- Si cambia la red de estaciones, la lista cambia sola con la regla.
