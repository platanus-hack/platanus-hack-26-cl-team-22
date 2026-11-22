# root

<img src="./project-logo.png" alt="Logo de root" width="160" />

**¿Qué pasa con una comuna si el plan no se cumple?**

root simula cómo evolucionan las 52 comunas de la Región Metropolitana de Santiago entre 2026 y 2036,
según los planes públicos que las afectan y **la probabilidad real de que se cumplan**. Ordena las comunas
por el riesgo que corre una inversión en ellas: ambiental, climático, social e institucional.

[Probar root](https://root-landing.onrender.com)

## El problema

Hoy puedes ver cómo está un barrio, pero no hacia dónde va. Los planes públicos prometen mejoras, pero no
todas se cumplen. Una revisión de 2023 del Plan de Descontaminación (PPDA) encontró que solo el 24 % de sus
medidas se cumplía y que el 55 % no tenía evidencia pública.

## Cómo funciona

- **Credibilidad de ejecución:** cada medida pesa según el historial real de cumplimiento de quien la
  ejecuta. Para los municipios, también cuenta lo que muestran sus licitaciones en ChileCompra.
- **Comunas conectadas:** el aire se mueve por la cuenca y los hogares se mudan entre comunas, llevándose la
  leña que queman.
- **Incertidumbre visible:** 500 réplicas por escenario. Siempre muestra una banda (p10–p90), nunca un número
  solo.
- **Tu caso, tus prioridades:** escribes tu situación con tus palabras («tengo un hijo con asma», «quiero
  instalar una bodega»). Claude elige uno de nueve perfiles de inversión y ajusta las prioridades, siempre
  dentro de un catálogo cerrado y citando la frase del caso que lo justifica. Claude nunca escribe números
  sobre las comunas.
- **Interruptor de políticas:** apaga una medida y ve cómo cambia el mapa.

## Hallazgos

PM2,5 en 2036, ponderado por población (norma anual: 20 µg/m³):

| Escenario | Mediana (p10–p90) |
|---|---|
| Ninguna política avanza | 22,9 |
| Planes vigentes, con el historial real de cumplimiento | **21,4** (20,2–22,4) |
| Planes vigentes, cumplidos al 100 % | **18,8** |

1. **El plan escrito deja la región bajo la norma. Con el cumplimiento observado, no la alcanza.**
2. **La migración puede borrar la mejora:** la ciudad se muda hacia la Zona B (+18 % de población al 2036) y,
   si la leña sigue a la gente, la región vuelve casi al nivel de hoy.
3. **Importa más quién ejecuta que cuántas promesas hay:** con 18 municipios ejecutando, la banda es de
   1,32 µg/m³; con un solo ejecutor, de 2,96 µg/m³.

## Validado contra datos que no vio

Cada mecanismo se ajusta con un período y se prueba con otro, contra dos alternativas simples («sin cambio» y
«tendencia»). Publicamos también dónde pierde:

| Variable | Prueba fuera de muestra | Gana |
|---|---|---|
| Aire | PM2,5 por estación 2022–2024 | **Modelo** (RMSE 1,91 vs 2,40) |
| Hogares | Migración neta por comuna 2019–2024 | **Modelo** |
| Población | Población por comuna 2024 | Sin cambio |
| Seguridad | Tasa de delitos a 2 años | **Modelo** |

## Datos

SINCA (PM2,5), RETC (emisiones), INE (censos 2017 y 2024), CEAD (delitos), DGA (caudales), ARClim (clima),
SEIA, SMA, ChileCompra y el seguimiento del PPDA.

## Stack

Python (NumPy, SciPy) para el modelo de Monte Carlo · React + TypeScript + MapLibre para el mapa en relieve ·
Claude Sonnet 5.5 en un servidor intermediario que lee el caso de cada persona.

## Equipo

- Jesus Rodolfo Gil Farias ([@Jrgil20](https://github.com/Jrgil20))
- Gabriel David Castellano Sierra ([@GdCastellano](https://github.com/GdCastellano))
- Daniel Enrique Bruno Silva ([@Holeekey](https://github.com/Holeekey))
- Valeria Riera ([@ingvaleriariera](https://github.com/ingvaleriariera))
- Massiel Paola Perozo Ballestero ([@massiperozo](https://github.com/massiperozo))
