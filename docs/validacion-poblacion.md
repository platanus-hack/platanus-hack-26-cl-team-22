# ¿Abrir el modelo de hogares proyecta mejor la población?

Estado al 21 de noviembre de 2026. Hoy el modelo de hogares es un sistema cerrado: la población
de la RM queda fija en 7,4 millones hasta 2036. Este experimento mide si agregarle nacimientos,
defunciones y flujos externos mejora la proyección por comuna. La comparación incluye la
proyección oficial del INE.

Código: `experiments/validar_poblacion.py`. Resultado: `results/poblacion_validacion.json`.

```
python -m experiments.validar_poblacion
```

## Prueba

Se parte de la población del censo 2017, se proyecta 7 años y se compara cada comuna con el
censo 2024. Las tasas salen solo de datos anteriores a 2017:

- nacimientos y defunciones: media de 2012 a 2016 (`data/vitales/`);
- flujos externos: censo 2017, el conteo quinquenal dividido por 5 (`data/censo/flujos_externos.csv`);
- mudanzas internas: matriz 2012→2017, igual que el modelo en producción.

## Resultado

Población real de la RM: 7.028.421 en 2017 y 7.400.741 en 2024.

| Proyección a 2024 | RMSE por comuna | Error % medio | Total RM | Correlación del crecimiento |
|---|---|---|---|---|
| Sin cambio (igual que 2017) | **15.046** | 8,2 % | 7.028.421 | — |
| Cerrado (modelo actual) | 16.904 | **5,9 %** | 7.028.421 | 0,22 |
| Abierto (este trabajo) | 18.472 | 9,1 % | 7.838.500 | 0,36 |
| Crecimiento oficial del INE (base 2017) | 18.391 | 6,8 % | 7.879.660 | **0,59** |
| Nivel oficial del INE, tal como se publica | 31.147 | 12,2 % | 8.420.729 | 0,49 |
| *Diagnóstico: abierto con nacimientos y defunciones reales 2017–2023* | *14.510* | — | *7.643.230* | *0,49* |

El diagnóstico usa datos del período de prueba, así que no es una predicción. Sirve para separar
de dónde viene el error.

## Qué significa

1. **En 7 años, ninguna proyección le gana a «sin cambio» en error por comuna.** Tampoco la del
   INE. Todas sobreestiman el crecimiento: la RM creció 372 mil personas, el modelo abierto
   esperaba 810 mil y el INE 851 mil.
2. **El modelo abierto rinde igual que la proyección oficial** en error (18.472 contra 18.391) y
   en total regional (7,84 contra 7,88 millones). Lo logra solo con censos y estadísticas
   vitales. El INE distingue mejor qué comunas crecen (0,59 contra 0,36), porque modela por edad.
3. **La sobreestimación tiene dos causas, de tamaño parecido:**
   - **Natalidad: unas 195 mil personas.** Los nacimientos cayeron de unos 100 mil al año
     (2012–2016) a 68.866 en 2023. Con los nacimientos reales, el error baja a 14.510 y le gana
     a «sin cambio».
   - **Migración: unas 243 mil personas.** Las salidas a otras regiones subieron de 294.886 a
     396.965 por quinquenio. Además, el censo no ve a quienes se van al extranjero, y la omisión
     del censo 2024 sería mayor que la de 2017 (dato de prensa, sin verificar en el INE).
4. **El modelo cerrado acierta mejor en error porcentual (5,9 %)** solo porque deja el total
   fijo y la RM creció poco. No es una virtud del modelo: su total queda 372 mil personas abajo.

## Qué cambia para proyectar a 2036

- **Usar las tasas recientes, no las de 2012–2017.** La caída de la natalidad ya ocurrió y se
  observa. Para 2026–2036 conviene usar la natalidad de 2022–2023 y las defunciones de 2019 y
  2022–2023, sin el exceso de 2020–2021 por COVID. Para los flujos externos, la matriz 2019→2024.
- **Mostrar el total regional con banda.** El supuesto de migración externa mueve el total en
  cientos de miles de personas en 10 años. Es incertidumbre real y no conviene esconderla en un
  solo número.
- **Comparar contra la proyección oficial base 2024 del INE** cuando publique la versión por
  comuna. Hoy solo existe a nivel país.
- **La métrica de personas expuestas sobre la norma depende de esto directamente**: población
  por comuna × concentración. Con el sistema cerrado subestima el total de la RM en 2036.

## Límites

- Las tasas son fijas por comuna y no tienen estructura por edad. El INE sí modela por edad, y
  por eso distingue mejor qué comunas crecen.
- `residencia_ignorada` (149.443 personas en 2017) no se asigna a ningún flujo.
- El período 2017–2024 incluye el estallido, la pandemia y la ola migratoria de 2018–2019. Una
  sola prueba de 7 años no alcanza para afirmar qué modelo es mejor en general.
- La proyección del INE corrige la omisión censal. Por eso se compara su crecimiento, aplicado
  a la población del censo, y también su nivel tal como se publica.
