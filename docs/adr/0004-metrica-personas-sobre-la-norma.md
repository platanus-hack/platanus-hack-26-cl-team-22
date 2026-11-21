# ADR-0004: La métrica de impacto es personas expuestas sobre la norma de PM2,5

- **Estado**: Aceptado
- **Fecha**: 2026-11-21

## Contexto

El impacto se evalúa por su escala. La métrica tiene que salir del modelo sin supuestos
extra que no podamos validar en 36 horas.

## Decisión

Impacto = personas que viven en comunas con PM2,5 anual simulado sobre la norma, usando la
población del censo 2024. Está en `impacto.por_escenario` de `viz/datos/simulacion.json`,
con p10, p50 y p90 por año.

## Alternativas consideradas

| Opción | Pros | Contras | Por qué se descartó |
|---|---|---|---|
| Costo en salud | Impacta en el pitch | Exige función dosis-respuesta y valoración | Supuestos no validables; queda como extensión |
| Muertes evitadas | Más concreto | Mismo problema que el costo | Extensión |
| Viviendas afectadas | Fácil de calcular | Menos intuitivo que personas | Agrega poco |

## Consecuencias

- La métrica salta en bloque: el modelo mueve las comunas casi en paralelo y cruzan la norma
  juntas. Hay que mostrarla como banda y explicar el salto.
- La escala de contexto (~4.000 muertes prematuras al año según el MMA) se cita como fuente
  externa, no como resultado del modelo.
