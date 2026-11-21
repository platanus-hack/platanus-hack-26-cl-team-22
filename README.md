# Simulador de comunas de la Región Metropolitana

<img src="./project-logo.png" alt="Logo del proyecto" width="160" />

Platanus Hack 26 · Santiago · team-22 · Track 🌐 Simulaciones

Proyecta el aire (PM2,5) de las 52 comunas de la Región Metropolitana entre 2026 y 2036 según
los planes públicos que las afectan y **la probabilidad real de que se cumplan**. Las comunas se
afectan entre sí de dos maneras: el aire se mueve por la cuenca y los hogares se mudan, llevando
consigo la leña que queman.

## La pregunta

**¿Qué pasa si el plan no se cumple?**

Cada medida del Plan de Descontaminación (PPDA, D.S. 31/2016) pesa según el historial de
cumplimiento de quien la ejecuta. Ese historial viene de una revisión medida por medida de
2023: 24 % conformes, 21 % parciales y 55 % sin evidencia pública. El modelo corre 500 réplicas
por escenario y muestra bandas, nunca un número solo.

## Hallazgos

PM2,5 en 2036, ponderado por población. Nivel de 2023: 23,1 µg/m³ (las 10 comunas con estación
parten de su medición). Norma anual: 20 µg/m³.

| Escenario | Mediana (p10–p90) |
|---|---|
| Ninguna política avanza | 22,9 |
| Planes vigentes, con el historial real de cumplimiento | **21,4** (20,2–22,4) |
| Planes vigentes, cumplidos al 100 % | **18,8** |
| Planes vigentes + prohibición de leña en la Zona B | 18,5 (15,6–21,1) |

1. **El incumplimiento como cifra.** El plan escrito deja la región bajo la norma. Con el
   cumplimiento observado no la alcanza.
2. **La migración puede borrar la mejora.** La ciudad se muda hacia la Zona B (+18 % de
   población en 2036). Si la leña sigue a la gente, con el plan vigente la región queda en 22,9,
   prácticamente el nivel de hoy.
3. **Importa más quién ejecuta que cuántas promesas hay.** Una planilla da 20,24 µg/m³ para
   todas las variantes de las 18 promesas de la Zona B. La simulación las separa:

   | Ejecución | Banda | Probabilidad de cumplir la norma |
   |---|---|---|
   | Un solo ejecutor | 2,96 µg/m³ | 0,51 |
   | 18 municipios | 1,32 µg/m³ | 0,54 |

   Lo robusto es la banda. La probabilidad de cumplir la norma depende de qué lado del umbral
   quede la mediana y su orden se invierte con cambios chicos de nivel (`docs/promesas.md`).
4. **Las políticas de seguridad casi no mueven la tasa comunal.** Con efectos citados de
   metaanálisis (cámaras y alumbrado reducen delitos contra la propiedad, no violentos),
   cobertura del 25 % y credibilidad municipal baja, las cámaras bajan los delitos de mayor
   connotación social entre 0,6 % y 1,0 % en las comunas intervenidas: muy dentro de la
   variación de un año a otro.

Detalle y supuestos: [`docs/modelo-aire.md`](docs/modelo-aire.md),
[`docs/modelo-hogares.md`](docs/modelo-hogares.md), [`docs/modelo-seguridad.md`](docs/modelo-seguridad.md),
[`docs/promesas.md`](docs/promesas.md).

## Validación

Cada mecanismo se ajusta con un período y se prueba con otro que no vio, contra alternativas
simples. También publicamos dónde pierde.

| Prueba fuera de muestra | Modelo | Alternativa simple |
|---|---|---|
| Aire: cambio medio 2017 → 2023 | −3,0 µg/m³ | Observado: −3,2 |
| Aire: niveles 2024, RMSE | 4,29 | Persistencia de 2023: **1,91** (gana la alternativa) |
| Aire v1: niveles 2024 anclados al nivel medido de cada estación | 1,91 | Persistencia: 1,91 (empate) |
| Hogares: migración neta 2019→2024, RMSE | **4.335** | Repetir 2012→2017: 5.054 · Nadie se muda: 7.716 |
| Seguridad: tasa DMCS 2024 a 2 años, error relativo (comunas fuera del ajuste) | **10,8 %** | Persistencia: 12,4 % · Tendencia: 13,1 % |
| Seguridad: tasa DMCS 2024 a 1 año | 8,5 % | Persistencia: **7,4 %** (gana la alternativa) |

El modelo de aire acierta cuánto mejora la región, pero todavía **no qué comunas ganan más**.
Donde hay estación (10 comunas), el nivel parte de lo medido y el modelo calcula el cambio.
Más detalle en [`docs/sim-spec.md`](docs/sim-spec.md#validación).

## Cómo ejecutar

```bash
make setup      # crea .venv e instala dependencias
make test       # 112 pruebas del núcleo y de los datos
make simulate   # calibra, simula y escribe viz/datos/simulacion.json (~15 s)
```

Para volver a descargar los datos crudos: `pip install -e ".[datos]"` y correr el script de
`datos/` de cada fuente (ver «Fuentes de datos»).

## Estructura

```
datos/        scripts de descarga (SINCA, RETC, censo, CEAD, PPDA)
data/         tablas limpias, con README de fuente, fecha y vacíos
core/         núcleo sin interfaz: aire, hogares, credibilidad y ciclo anual
experiments/  calibración, comparación de promesas y simulación
results/      resultados de validación, cada uno con el comando que lo reproduce
viz/          interfaz: solo lee viz/datos/simulacion.json
docs/         spec, modelo y decisiones del proyecto
```

## Fuentes de datos

- SINCA (MMA): PM2,5 por estación.
- RETC: emisiones por comuna y fuente.
- INE: Censos 2017 y 2024.
- CEAD: delitos por comuna.
- ECOS-Chile y la SMA: cumplimiento del PPDA.

Cada una con su URL, fecha de descarga y vacíos en el README de su carpeta de `data/`. Las
emisiones todavía no tienen README: su fuente (datos abiertos del RETC) está documentada en
`datos/emisiones/build_emisiones.py`.

## Equipo

- Jesus Rodolfo Gil Farias ([@Jrgil20](https://github.com/Jrgil20))
- Gabriel David Castellano Sierra ([@GdCastellano](https://github.com/GdCastellano))
- Daniel Enrique Bruno Silva ([@Holeekey](https://github.com/Holeekey))
- Valeria Riera ([@ingvaleriariera](https://github.com/ingvaleriariera))
- Massiel Paola Perozo Ballestero ([@massiperozo](https://github.com/massiperozo))

Documentos del equipo: [`docs/plan-comunas.md`](docs/plan-comunas.md) ·
[`docs/contexto-proyecto.md`](docs/contexto-proyecto.md) · [`docs/work-plan.md`](docs/work-plan.md)
