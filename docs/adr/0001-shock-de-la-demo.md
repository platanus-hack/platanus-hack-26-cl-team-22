# ADR-0001: El shock de la demo es la leña del plan de descontaminación

- **Estado**: Aceptado
- **Fecha**: 2026-11-21

## Contexto

La demo necesita un cambio fechado y medible que muestre interacción entre comunas. La prueba
de la brecha (`docs/plan-comunas.md`, 21 nov) midió que un proyecto local del SEIA mueve el
aire ±0,2 µg/m³: no se nota. La leña es el 60 % de las emisiones reguladas, y el 77 % de las
emisiones de leña está en la Zona B, donde el plan (D.S. 31/2016, vigente desde el
24-nov-2017) solo restringe calefactores nuevos (art. 75), mientras en la Zona A los prohíbe
(art. 74).

## Decisión

La demo usa dos interruptores sobre la leña, los dos ya precalculados en
`viz/datos/simulacion.json`:

1. **Paso 3 (apagar)**: `sin-ppda-lena-zona-a`. Talagante (Zona B, no ejecuta la medida)
   empeora de 20,5 a 21,5 µg/m³ en 2036 (p50).
2. **Paso 4 (hallazgo)**: `con-propuesta-lena-zona-b`. Una medida que se ejecuta en la
   periferia mejora comunas urbanas: El Bosque baja de 26,3 a 23,2 µg/m³ y Las Condes de
   17,5 a 15,0 (p50, 2036). La banda se ensancha (El Bosque 19,9–26,2) porque la medida no
   tiene historial de cumplimiento.

## Alternativas consideradas

| Opción | Pros | Contras | Por qué se descartó |
|---|---|---|---|
| Proyecto aprobado en el SEIA | Fechado, real | ±0,2 µg/m³, invisible en el mapa | No se nota en la demo |
| Línea de Metro | Fácil de contar | El modelo no tiene transporte por línea | Fuera del alcance del MVP |
| Migración desde Venezuela | Tema conocido | Contradice "sin inmigración como variable de riesgo" | Queda como extensión |

## Consecuencias

- El titular de la demo es la trayectoria de cada comuna y de qué depende, no un ranking
  que se reordena: las políticas casi no cambian el orden (Spearman ≥ 0,97).
- La magnitud de la Zona B sale de un modelo de aire anclado a estaciones; hay que decirla
  como banda, no como número.
- Las cifras de este ADR cambian si se recalcula `make simulate`; la demo debe leerlas del
  JSON, no de este texto.
