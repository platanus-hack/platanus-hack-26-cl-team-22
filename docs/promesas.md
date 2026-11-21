# Muchas promesas o mucha ejecución

Estado al 21 de noviembre de 2026. Pregunta: **¿da lo mismo prometer mucho y cumplir poco que
prometer poco y cumplirlo?** Código en `experiments/promesas.py`; resultado en
`results/promesas.json` y en la clave `promesas` de `viz/datos/simulacion.json`.

Reproducir (unos 60 segundos):

```
python -m experiments.promesas
```

## Por qué esta comparación

El track descalifica «una proyección que sale de una fórmula o de una planilla». La prueba más
directa es tomar dos planes que **una planilla da por iguales** y mostrar en qué los separa la
simulación.

## Diseño

Los dos paquetes atacan la leña de la Zona B del PPDA, la palanca principal del modelo de aire
(77 % de la leña regional). Se parte de las emisiones de 2023 sin otras políticas, para aislar la
comparación.

| Paquete | Medidas | Credibilidad media | Origen de la credibilidad |
|---|---|---|---|
| Muchas promesas | Prohibir la leña en cada una de las 18 comunas de la Zona B | 0,347 | Tasa base del PPDA (ECOS-Chile 2023, lectura conservadora) |
| Pocas promesas | Una medida: reducir 43,4 % la leña de la Zona B | 0,8 | **Supuesto**: ejecutor creíble hipotético; no sale de una fuente |

El 43,4 % no se ajustó mirando el resultado: es el valor con el que una planilla los iguala,
`credibilidad × reducción prometida`: 0,347 × 100 % = 0,8 × 43,4 %.

Las muchas promesas se corren con dos estructuras de ejecutor: **un solo ejecutor regional** o
**cada comuna con su municipio**. Ver `docs/credibilidad.md` para cómo se correlacionan.

## Resultado

PM2,5 en 2036, promedio ponderado por población, 2.000 réplicas. Nivel 2023: 23,4 µg/m³;
norma anual: 20 µg/m³. La planilla da **20,57** para los tres.

| Paquete | Mediana | Mejor caso (p10) | Peor caso (p90) | Ancho de banda | Prob. de cumplir la norma |
|---|---|---|---|---|---|
| Muchas promesas, un ejecutor | 20,29 | 18,73 | **21,69** | **2,96** | 0,41 |
| Muchas promesas, 18 municipios | 20,27 | 19,60 | 20,92 | 1,32 | **0,29** |
| Pocas promesas | 20,21 | **19,86** | 21,27 | 1,41 | 0,42 |

Qué significa:

1. **La mediana sí es la de una planilla** (las tres quedan en 20,2–20,3). Lo decimos: el valor
   central de este modelo sale de una cuenta simple. Lo que no sale de una cuenta es lo de abajo.
2. **Importa más quién ejecuta que cuántas promesas hay.** Las mismas 18 promesas tienen una
   banda de 2,96 µg/m³ con un solo ejecutor y de 1,32 con 18 municipios: cuando las medidas
   dependen del mismo ejecutor, fallan juntas y prometer más no reparte el riesgo.
3. **Menos riesgo no es más probabilidad de cumplir.** Repartir entre municipios da la banda
   más estrecha y la menor probabilidad de cumplir la norma (0,29 frente a 0,41). La mediana
   queda justo sobre 20; sin varianza casi ninguna réplica baja de la norma. Es un efecto de
   umbral que una planilla no puede mostrar.
4. **La promesa chica tiene techo.** Su mejor caso (19,86) es exactamente lo prometido: nunca
   sorprende para bien. Por eso su media es la peor de las tres aunque su mediana sea la mejor.

## De qué depende

| Variante | Muchas, un ejecutor | Muchas, 18 municipios | Pocas promesas |
|---|---|---|---|
| Principal (`ρθ = 0,5`, rampa de 10 años): banda / prob. norma | 2,96 / 0,41 | 1,32 / 0,29 | 1,41 / 0,42 |
| Credibilidad independiente (`ρθ = 0`) | 1,83 / 0,35 | 1,34 / 0,28 | 1,41 / 0,42 |
| Rampa de 5 años | 4,13 / 0,89 | 1,87 / 1,00 | 0,00 / 0,98 |

- Con `ρθ = 0` la diferencia entre un ejecutor y 18 municipios se achica, pero se mantiene
  (por la correlación anual `ρ = 0,3`), y el orden de las probabilidades no cambia.
- **La rampa cambia qué significa la credibilidad.** Con 10 años para el efecto completo, una
  credibilidad de 0,347 entrega cerca de 35 % de lo prometido, que es lo que mide ECOS-Chile.
  Con 5 años, la misma credibilidad entrega cerca de 76 %, y la comparación deja de ser justa.
  La rampa de 10 años sigue el horizonte del PPDA (art. 1); es un supuesto y queda a la vista.

## Límites

- La comparación no incluye el mecanismo de hogares: la población queda fija, para aislar el
  efecto de cómo se promete y se ejecuta.

- Usa el modelo de aire v0: todas las comunas se mueven casi igual, así que el resultado es
  regional. No dice qué comunas ganan más con cada paquete.
- La credibilidad alta (0,8) es hipotética. La conclusión 2 no depende de ella; las
  conclusiones 3 y 4 comparan contra ella.
- Esto mejora la demo, pero no reemplaza lo que más convierte el proyecto en simulación: el
  lazo de hogares (la gente se muda, cambian las emisiones) y una segunda variable para que los
  pesos tengan efecto.
