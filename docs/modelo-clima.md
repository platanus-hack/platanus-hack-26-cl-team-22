# Modelo de riesgo climático

Estado al 21 de noviembre de 2026. Código en `core/clima.py`; exportación en
`experiments/simular.py` (bloque `clima` de `viz/datos/simulacion.json`); validación en
`experiments/validar.py` (`docs/validacion.md`, sección «Riesgo hídrico contra los decretos de
escasez»). Datos: series de ARClim por comuna y corrida de modelo climático en `data/arclim/`
(ver su README).

Reproducir:

```
make simulate   # bloque clima
make validate   # prueba contra los decretos de la DGA
```

## Qué calcula

ARClim es insumo, no resultado. Cada réplica sortea un modelo climático (GCM) y una de sus
corridas, y el motor calcula, por comuna y año, cuánto cambia cada indicador respecto de
1991-2020 **en esa misma corrida**. Se usan cambios porque los niveles absolutos de los modelos
tienen sesgo.

| Riesgo | Indicador | Cambio |
|---|---|---|
| Hídrico | `pr_sum`, precipitación anual | % |
| Hídrico | `drought_periods`, frecuencia de sequía | puntos porcentuales |
| Inundación | `maximum_daily_precipitation`, precipitación máxima diaria | % |
| Inundación | `days_over_50mm`, días sobre 50 mm | días |
| Calor | `hot_days`, días sobre 30 °C | días |
| Calor | `degdays_above_25`, grados-día sobre 25 °C | grados-día |

Se exportan p10, p50 y p90 entre las 500 réplicas, para 2026-2060 y para los escenarios SSP2-4,5
y SSP5-8,5.

## Supuestos

- **Un mismo mundo climático por réplica.** El sorteo elige entre las 19 corridas que traen los
  seis indicadores (17 modelos en SSP2-4,5, 18 en SSP5-8,5). Primero sortea el modelo con igual
  probabilidad y después una de sus corridas, para que un modelo con más corridas no pese más.
  Usa su propia semilla, así que no cambia ninguna otra salida de la simulación.
- **Ventana de 20 años.** El valor de cada año es la media de la corrida entre ese año menos 10
  y ese año más 9 (la misma longitud que el 2041-2060 de ARClim). Por eso el último año es 2060:
  su ventana termina en 2069, el último año de las series.
- **Sin índice compuesto.** Cada riesgo muestra sus componentes en su propia unidad. Sumarlos
  exigiría pesos que nadie midió.
- **Sin evapotranspiración.** `eto_mean` queda fuera porque solo la traen 10 modelos.

Ejemplo, Santiago (SSP2-4,5, 2041-2060): días sobre 30 °C +23 / +40 / +51 (p10 / p50 / p90),
precipitación anual −20 / −5 / +5 %. El README de ARClim da 71,0 → 107,6 días sobre 30 °C
para el promedio de modelos.

## Validación: no le gana a una alternativa simple

Los años de un modelo climático no corresponden a años reales, así que la prueba compara
comunas: ¿el cambio de la frecuencia de sequía ordena primero a las 24 comunas con decreto de
escasez de la DGA (2008-2023)? El indicador se fijó antes de ver el resultado.

- Modelo: AUC 0,61, p 0,09 por permutación. **No se distingue del azar.**
- «Fuera de la provincia de Santiago»: AUC 0,92.
- La lluvia modelada de 1991-2020 ordena al revés: las comunas con decreto son las más lluviosas.

Lectura: los decretos probablemente siguen a la **exposición** (comunas rurales, riego, agua de
pozo) más que al cambio del clima. El motor mide cuánto cambia el clima de cada comuna, no
cuán expuesta está hoy. Falta un componente de exposición antes de usar el riesgo hídrico para
ordenar comunas.

## Fuera de alcance por ahora

- Mostrar el riesgo climático en el ranking de la interfaz (`viz/`), el catálogo de
  `caso.ts` y las instrucciones de `servidor-guia`. Es una decisión de producto pendiente.
- Acoplar los grados-día de calefacción al modelo de aire: cambiaría salidas ya validadas.
