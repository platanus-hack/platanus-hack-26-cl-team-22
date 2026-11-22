# Simulación de mudanzas por agentes: saturación y derrame

Estado al 21 de noviembre de 2026. Es la simulación de la sección «Desarrollo urbano: quién se muda a dónde» (pestaña Social). Reemplaza
el prototipo determinista de `viz/src/lib/demografia.ts`, que solo multiplicaba tasas.

## Pregunta

**Si la vivienda se llena y cada grupo llega a donde llegaron los suyos, ¿qué comunas se saturan
primero y hacia dónde se derrama la gente?**

## Clasificación (5 ejes)

| Eje | Valor | Consecuencia |
|---|---|---|
| Tiempo | Dinámica | Ciclo anual de 2024 a 2036 |
| Cambio de estado | Discreta, a paso anual | `paso()` por año. Dentro del año, las decisiones se procesan en orden aleatorio y cada una consume vivienda libre |
| Incertidumbre | Estocástica | PRNG con semilla, réplicas y bandas p10–p90 |
| Acoplamiento | Constructiva, con eventos del usuario | El usuario dispara eventos entre años; el estado autoritativo vive en el motor (Web Worker) |
| Representación | Basada en agentes | Agentes con reglas que dependen del estado: la saturación y las concentraciones emergen |

## Paradigma

ABM liviano. Prueba DES/ABM: si se les quita la decisión a los agentes (destino fijo), no hay
derrame ni concentraciones que se refuercen. La decisión es el mecanismo, así que es ABM.

## Entidades y estado

- **Agente** = grupo de `tamano_grupo` personas (por defecto 250; unos 30 mil agentes).
  - Estado: `comuna` (índice), `origen`: `local` | `otra_region` | `extranjero`, y `anio_llegada`.
- **Comuna** (52).
  - Estado: `capacidad` en personas, `ocupadas` (personas) y `stock_extranjero` (personas que
    llegaron del extranjero, incluida la población inicial nacida en el extranjero).
- **Capacidad inicial** = viviendas del censo 2024 × personas por vivienda ocupada de la comuna
  en 2024. Crece cada año con `permisos_anuales[j]` × personas por vivienda.

## Reglas de un año

Todo se decide sobre el estado al **inicio** del año (`P[i]` = personas en `i`), como el modelo
determinista, para que el promedio de muchas réplicas lo reproduzca.

1. **Capacidad**: `capacidad[j] += permisos_anuales[j] · personas_por_vivienda[j] · mult_vivienda[j]`.
2. **Un sorteo por agente** (riesgos que compiten), con probabilidades de su comuna `i`:
   - muere: `mortalidad[i]`;
   - se va de la región: `salen_regiones[i]`;
   - busca mudarse dentro de la región: `tasa_salida[i]`;
   - se queda: el resto.
3. **Nacimientos**: en cada comuna nacen `Poisson(natalidad[i] · P[i] / tamano_grupo)` grupos
   locales. Ocupan vivienda de su comuna aunque esté llena; la sobreocupación se registra.
4. **Llegadas externas**:
   - desde otras regiones: `Poisson(Σ_j llegan_regiones[j] · P[j] / tamano_grupo)` grupos;
   - desde el extranjero: `Poisson(Σ_j llegan_extranjero[j] · P[j] / tamano_grupo · mult_ola)`.
5. **Elección de destino**:
   - Quienes buscan destino (internos y externos) se procesan **en orden aleatorio**.
   - Cada uno elige entre las comunas con vivienda libre (`capacidad − ocupadas ≥ tamano_grupo`),
     con peso `w_j`:
     - mudanza interna desde `i`: `w_j = destinos[i][j]` (proporciones observadas, `j ≠ i`);
     - desde otra región: `w_j = llegan_regiones[j] · P[j]` (geografía medida);
     - desde el extranjero, modo `fijo`: `w_j = llegan_extranjero[j] · P[j]`;
     - desde el extranjero, modo `redes`: `w_j = (stock_extranjero[j] + 1)^φ`.
   - Al instalarse, `ocupadas[j]` sube y, si viene del extranjero, también `stock_extranjero[j]`.
     **Esa es la retroalimentación**: cada llegada hace más atractiva su comuna para la siguiente.
   - **Derrame**: una comuna llena sale del sorteo y su peso se reparte entre las demás. Si
     ninguna tiene lugar, el agente interno se queda donde estaba y el externo no llega; ambos
     se cuentan como **demanda no atendida**.
6. **Registro del año**:
   - población por comuna;
   - flujos origen → destino;
   - comunas saturadas;
   - derrames: agentes cuyo destino de mayor peso estaba lleno;
   - demanda no atendida.

Con capacidad infinita y el modo `fijo`, el valor esperado de cada componente es igual al del
modelo determinista (`experiments/validar_poblacion.py`). Esa es la prueba de paridad.

## Eventos del usuario (entre años)

- `ola_migratoria`: multiplica λ_extranjero por `m` durante `n` años.
- `densificar`: multiplica los permisos de una comuna por `m`.
- `crisis`: multiplica `tasa_salida` y las llegadas por `m` durante `n` años.

## Parámetros

| Nombre | Origen |
|---|---|
| `tasa_salida`, `destinos` | Matriz censal 2012→2017 (igual que `core/hogares.py`) |
| `natalidad`, `mortalidad`, `llegan_*`, `salen_regiones` | `experiments/exportar_demografia.py` (tasas recientes) |
| `stock_extranjero` inicial | Nacidos en el extranjero por comuna. Se aproxima con el censo 2017 y se anota |
| `φ` (redes) | **Ajustado**: stock antes de 2012 → llegadas 2012–2017; probado: stock 2017 → llegadas 2019–2024 (`experiments/validar_redes.py`) |
| `permisos_anuales` | Media 2015–2024 de `data/vivienda/permisos_vivienda.csv` |
| `personas_por_vivienda` | Población 2024 / viviendas particulares ocupadas 2024 |

## Validación

1. **Paridad en el promedio**: con capacidad infinita y el modo `fijo`, la media de muchas
   réplicas reproduce la proyección determinista validada (`referencia.por_defecto`) dentro de
   una tolerancia estadística.
2. **Reproducibilidad**: misma semilla, misma trayectoria; otra semilla, otra trayectoria.
3. **Contabilidad**: población[t+1] = población[t] + nacimientos − defunciones + llegadas − salidas.
4. **Capacidad**: con capacidad finita, ninguna llegada por mudanza deja una comuna sobre su
   capacidad (los nacimientos sí pueden, y se registran).
5. **Regla de redes fuera de muestra**: `φ` ajustado en 2012–2017 se prueba con 2019–2024, contra
   «misma geografía que el período anterior» y contra «proporcional a la población».

## Supuestos

- Grupos de personas, no hogares (el censo cuenta personas).
- Sin estructura por edad. Las tasas son fijas por comuna salvo los eventos.
- El aire no cambia a dónde se muda la gente (no identificable con los censos;
  `docs/modelo-hogares.md`).
- La capacidad es vivienda física. Los permisos se cuentan como viviendas habitables, con rezago 0
  en la proyección.

## Implementación y primeros resultados

Motor: `viz/src/lib/mudanzasAbm.ts`, con PRNG con semilla en `viz/src/lib/prng.ts`. Pruebas:
`viz/src/lib/mudanzasAbm.test.ts` (paridad, reproducibilidad, contabilidad, capacidad, redes y
eventos). Parámetros: `abm` en `viz/public/datos/demografia.json`
(`python -m experiments.exportar_demografia`). Una corrida de 12 años con grupos de 250
personas tarda unos 50 ms.

Con los parámetros reales, modo `redes` (φ = 1,086) y 20 réplicas:

| Escenario | RM 2036 (p10–p50–p90) | Comunas saturadas por corrida | Grupos derramados | Demanda no atendida |
|---|---|---|---|---|
| Base | 8,02 – 8,06 – 8,11 millones | ~10 | 91 | 0 |
| Ola migratoria ×3 en 2026–2028 | 8,48 – 8,52 – 8,55 millones | ~21 | 311 | 0 |
| Permisos congelados desde 2025 | 7,93 millones | 52 | 3.722 | 1.664 grupos (~416 mil personas) |

- **Escenario base:** casi siempre se saturan comunas de la periferia (Lampa, Pirque, María
  Pinto, Curacaví, Paine, Talagante). La demanda que reciben supera la vivienda que autorizan.
- **Con la ola migratoria** se suman Colina e Independencia. Independencia es un foco de llegadas
  desde el extranjero, y el efecto de redes concentra ahí la demanda nueva.
- **Sin permisos nuevos**, la región entera se llena y cerca de 416 mil personas no encuentran
  dónde instalarse en 12 años.

Son resultados del modelo con sus supuestos. La capacidad cuenta vivienda física, no precios ni
hacinamiento.
