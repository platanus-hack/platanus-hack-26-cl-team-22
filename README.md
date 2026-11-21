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

PM2,5 en 2036, ponderado por población. Nivel de 2023: 23,4 µg/m³. Norma anual: 20 µg/m³.

| Escenario | Mediana (p10–p90) |
|---|---|
| Ninguna política avanza | 23,2 |
| Planes vigentes, con el historial real de cumplimiento | **21,7** (20,5–22,7) |
| Planes vigentes, cumplidos al 100 % | **19,1** |
| Planes vigentes + prohibición de leña en la Zona B | 18,8 (15,8–21,4) |

1. **El incumplimiento como cifra.** El plan escrito deja la región bajo la norma. Con el
   cumplimiento observado no la alcanza.
2. **La migración puede borrar la mejora.** La ciudad se muda hacia la Zona B (+18 % de
   población en 2036). Si la leña sigue a la gente, con el plan vigente la región queda en 23,2,
   prácticamente el nivel de hoy.
3. **Importa más quién ejecuta que cuántas promesas hay.** Una planilla da 20,57 µg/m³ para
   todas las variantes de las 18 promesas de la Zona B. La simulación las separa:

   | Ejecución | Banda | Probabilidad de cumplir la norma |
   |---|---|---|
   | Un solo ejecutor | 2,96 µg/m³ | 0,41 |
   | 18 municipios | 1,32 µg/m³ | 0,29 |

Detalle y supuestos: [`docs/modelo-aire.md`](docs/modelo-aire.md),
[`docs/modelo-hogares.md`](docs/modelo-hogares.md), [`docs/promesas.md`](docs/promesas.md).

## Validación

Cada mecanismo se ajusta con un período y se prueba con otro que no vio, contra alternativas
simples. También publicamos dónde pierde.

| Prueba fuera de muestra | Modelo | Alternativa simple |
|---|---|---|
| Aire: cambio medio 2017 → 2023 | −3,0 µg/m³ | Observado: −3,2 |
| Aire: niveles 2024, RMSE | 4,29 | Persistencia de 2023: **1,91** (gana la alternativa) |
| Hogares: migración neta 2019→2024, RMSE | **4.335** | Repetir 2012→2017: 5.054 · Nadie se muda: 7.716 |

El modelo de aire acierta cuánto mejora la región, pero todavía **no qué comunas ganan más**.
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
