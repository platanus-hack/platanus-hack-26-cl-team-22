# ADR-0006: El usuario principal es el inversionista

- **Estado**: Aceptado
- **Fecha**: 2026-11-21
- **Reemplaza**: ADR-0003 en la elección del usuario principal

## Contexto

El ADR-0003 puso al municipio como usuario principal y al ciudadano como cara humana. Después,
el equipo definió que el objetivo del producto es atraer capital internacional, pero esa
decisión quedó solo en el traspaso de sesión y no en un documento del repositorio.

Quien invierte en una comuna hace preguntas que el municipio no hace:

- ¿Qué tan expuesto queda el activo al clima? Responde el bloque `clima` de `simulacion.json`
  (`docs/modelo-clima.md`).
- ¿Qué tan probable es que el proyecto se trabe antes de construirse? En la Región
  Metropolitana, cerca de 2.050 de 5.236 proyectos del SEIA no llegaron a aprobarse
  (desistidos, no admitidos, rechazados y otros; `data/seia/README.md`).
- ¿Qué pasa si los planes públicos no se cumplen? Responde el interruptor de políticas con su
  credibilidad.

## Decisión

El usuario principal es el inversionista. El producto ordena comunas por el riesgo que corre
una inversión en ellas: ambiental (aire), social (seguridad, población), climático e
institucional.

Se mantiene del ADR-0003:

- El interruptor de políticas y la barra de credibilidad. Para el inversionista responden
  «¿qué pasa si el plan no se cumple?».
- Una sola pantalla, sin chats ni tableros.
- Los pesos solo reordenan resultados ya calculados; no son simulación.

## Alternativas consideradas

| Opción | Pros | Contras | Por qué se descartó |
|---|---|---|---|
| Municipio como usuario principal (ADR-0003) | Es quien decide y fiscaliza los planes | No es quien pone el capital | El objetivo del equipo es atraer capital internacional |
| Ciudadano o comprador como usuario principal | Público amplio y cercano | Su pregunta es dónde vivir, no dónde invertir | Ya se descartó en el ADR-0003 |

## Consecuencias

- El riesgo institucional (SEIA y SMA) entra en el alcance: mide el riesgo de que un proyecto
  no se apruebe o sea sancionado.
- El riesgo climático tiene que llegar a la interfaz. Hoy la interfaz no lee el bloque `clima`.
- Los cuatro perfiles de `tipos_hogar` están pensados para elegir dónde vivir. Hay que revisar
  si sirven a un inversionista o se reemplazan por perfiles de inversión.
- Las instrucciones de `servidor-guia` y el catálogo de `caso.ts` interpretan casos personales
  («mi hijo tiene asma»). Hay que revisarlos para casos de inversión.
- El riesgo hídrico todavía no se puede usar para ordenar comunas: no le gana a «fuera de la
  provincia de Santiago» contra los decretos de la DGA (`docs/validacion.md`).
