# ADR-0003: El municipio simula; el ciudadano lee con perfiles

- **Estado**: Aceptado
- **Fecha**: 2026-11-21

## Contexto

La pregunta central es "¿qué pasa si este plan no se cumple?". La pregunta la hace quien
decide o fiscaliza planes. La persona que elige dónde vivir necesita otra cosa: ordenar
comunas según lo que le importa. Restricción del equipo: nada de chats ni tableros.

## Decisión

- **Usuario principal: el municipio.** Usa el interruptor de políticas, al centro de la
  interfaz, para simular.
- **Cara humana: el comprador o ciudadano**, en el paso 6 de la demo. Elige uno de los cuatro
  perfiles de `tipos_hogar` (sensible a la contaminación, prioriza seguridad, prefiere
  comunas que crecen, equilibrado) o mueve tres pesos; la lista de comunas se reordena en el
  navegador sin recalcular.
- **La confianza sale del mismo interruptor**, no de un módulo de auditoría. Cada política
  muestra su barra de credibilidad, y los escenarios `base-plan-escrito` (todo se cumple) y
  `base-lectura-optimista` muestran cuánto cambia el resultado si se cree el plan tal como
  está escrito. En El Bosque la diferencia en 2036 es 23,4 contra 26,3 µg/m³ (p50).

## Alternativas consideradas

| Opción | Pros | Contras | Por qué se descartó |
|---|---|---|---|
| Comprador como usuario principal | Más cercano al público | El interruptor de políticas no es su decisión | Debilita la pregunta central |
| Módulo de auditoría separado | Explícito | Otra pantalla, más fricción | La credibilidad ya está en cada política |

## Consecuencias

- Una sola pantalla sirve a los dos usuarios.
- Los pesos solo reordenan resultados ya calculados: no son simulación y no deben venderse
  como tal.
