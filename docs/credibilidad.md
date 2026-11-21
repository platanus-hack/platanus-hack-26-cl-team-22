# Credibilidad de ejecución

Estado al 21 de noviembre de 2026. Describe cómo el modelo decide qué medidas de un plan se
ejecutan cada año simulado. Implementación: `core/credibilidad.py`. Contexto general en
[`contexto-proyecto.md`](./contexto-proyecto.md).

## El problema

Un plan público describe lo que **debería** pasar. En Chile y en LATAM, lo que pasa suele ser
distinto: medidas que llegan tarde, que se hacen a medias o que no se hacen. Si el simulador
asume que el plan se cumple tal como está escrito, solo repite el documento oficial.

La credibilidad de ejecución es la probabilidad de que una medida se ejecute, estimada con el
historial de quien la ejecuta. Es el diferencial del proyecto, y por eso tiene que poder
defenderse con datos y con una validación publicada.

## Qué modela el MVP

Para cada medida y cada año simulado, el modelo decide si la medida **se ejecuta ese año**
(sí o no). Si se ejecuta, aplica su efecto del catálogo de intervenciones; si no, no aplica nada.

**Segunda iteración (fuera del MVP):** la falla típica en LATAM no es «no se hace nunca», sino
«se hace tarde y a medias». Quedan pendientes dos dimensiones más por medida:

- **Retraso**: años entre la fecha comprometida y la ejecución real.
- **Fracción ejecutada**: parte del efecto prometido que efectivamente ocurre.

## De dónde sale la credibilidad

Cada medida tiene una distribución Beta sobre su probabilidad anual de ejecución, θ.

1. **Tasa base del tipo de ejecutor** (previa): `Beta(α0, β0)`. Hay un tipo por clase de
   ejecutor (ministerio o servicio regional, municipio, privado con proyecto en el SEIA).
2. **Historial propio de la medida o del ejecutor**: `k` medidas o hitos cumplidos de `n`
   comprometidos.
3. **Credibilidad final** (posterior, modelo Beta-Binomial):

   ```
   θ ~ Beta(α0 + k, β0 + n − k)
   ```

Consecuencias:

- **Con historial** (por ejemplo, el PPDA con los informes de avance de la SMA): la banda se
  estrecha alrededor del cumplimiento observado.
- **Sin historial** (por ejemplo, planes comunales de seguridad): la banda queda ancha y
  centrada en la tasa base del tipo de ejecutor.

Cada credibilidad lleva su **procedencia**, que la interfaz muestra:

| Procedencia | Significado |
|---|---|
| `medida` | Historial propio de la medida o de su ejecutor |
| `tasa_base` | Sin historial propio; se usa la tasa base de su tipo de ejecutor |
| `supuesto` | No hay dato todavía; valor elegido por el equipo y pendiente de reemplazar |

Las tasas base son supuestos hasta que el frente 5 las estime. No van en `data/`, que no admite
números inventados.

## Dos niveles de azar

| Nivel | Qué representa | Cuándo se sortea |
|---|---|---|
| θ (credibilidad) | Lo que no sabemos sobre el ejecutor | **Una vez por réplica** |
| Ejecución | El azar de cada año | **Una vez por año**, con θ fijo |

Si θ se sorteara cada año, los años buenos y malos se compensarían dentro de una misma réplica y
las bandas saldrían falsamente estrechas.

## Las fallas van juntas

Cuando un municipio recorta presupuesto o cambia de administración, fallan varias de sus
medidas a la vez. Sorteos independientes por medida subestiman ese riesgo.

El modelo usa una **cópula gaussiana de un factor**. Para la medida `i` del ejecutor `e` en el
año `t`:

```
latente[i, t] = √ρ · z[e, t] + √(1 − ρ) · ε[i, t]        z, ε ~ Normal(0, 1)
la medida se ejecuta si  latente[i, t] < Φ⁻¹(θ_i)
```

- `z[e, t]` es el shock común del ejecutor en ese año; `ε[i, t]` es propio de la medida.
- La probabilidad de ejecutarse sigue siendo exactamente θ: el shock cambia **con quién** falla
  una medida, no **cuánto** falla. Eso mantiene válida la calibración.
- `ρ = 0` equivale a sorteos independientes. θ = 0 nunca se ejecuta y θ = 1 siempre.
- **Supuesto:** `ρ = 0,3` por defecto, hasta poder estimarlo con el historial.

Pendiente: un shock común a todos los ejecutores para años atípicos (2019, 2020 y 2021).

## Atribución con números aleatorios comunes

El aporte de una política es «simulación con la política − simulación sin ella». Esa resta solo
mide la política si **el resto del azar es idéntico** en ambos escenarios.

Por eso cada medida y cada ejecutor tienen su propio flujo de números aleatorios, derivado de
`(semilla, réplica, identificador)`. No depende de la posición en una lista: agregar o quitar una
medida no cambia los sorteos de las demás. Un escenario solo deja medidas afuera; nunca vuelve a
sortear.

## Validación

| Pregunta | Qué hacemos | Qué mostramos |
|---|---|---|
| ¿La credibilidad predice? | Ajustar con los informes de la SMA 2017–2020 y predecir el cumplimiento 2021–2024 del PPDA (depende de conseguir el detalle por año; la revisión de ECOS-Chile es una sola foto de 2023) | Error sobre años que el ajuste no vio |
| ¿Está calibrada? | Agrupar medidas por credibilidad y comparar con su cumplimiento real | Diagrama de calibración y Brier score: de las medidas al 70 %, se cumple cerca del 70 % |
| ¿Es mejor que lo obvio? | Comparar contra «todo se cumple» (lo que asume el plan oficial) y «nada se cumple» | Cuánto gana el modelo frente a cada alternativa |

La comparación contra «todo se cumple» es además un titular de la demo: «el plan oficial
proyecta X; con el historial real de cumplimiento se proyecta Y». La diferencia es el
incumplimiento como cifra.

## Fuente principal: revisión medida por medida del PPDA

Una revisión encargada por la SEREMI RM (ECOS-Chile, 2023) evalúa las 157 medidas del PPDA una
por una: **24 % conformes, 21 % parciales y 55 % sin evidencia pública** (ver
[`plan-comunas.md`](./plan-comunas.md)). Es la base para calcular la credibilidad con datos
reales. Cómo se traduce al modelo:

| Estado en la revisión | En el MVP | Comentario |
|---|---|---|
| Conforme | Cuenta como cumplida (`k`) | |
| Parcial | Cuenta como cumplida a medias | Es justo la «fracción ejecutada» de la segunda iteración. Mientras tanto, se prueba contándola como cumplida y como no cumplida |
| Sin evidencia pública | **Supuesto explícito** | Falta de evidencia no es prueba de incumplimiento. Se informa el resultado con dos lecturas: «sin evidencia = no cumplida» y «sin evidencia = se excluye del conteo» |

Que más de la mitad de las medidas no tenga evidencia pública es en sí un hallazgo sobre
rendición de cuentas. El modelo no lo esconde: muestra cuánto cambia la proyección según
cómo se lea ese 55 %.

## Fuentes candidatas (todas por verificar)

| Fuente | Para qué | Pendiente |
|---|---|---|
| Informes de avance del PPDA RM (SMA) | Historial del plan de aire | El informe 2024 agrega por categoría; el detalle por medida está en un anexo Excel que no se pudo obtener |
| Contraloría, planes comunales de seguridad 2024–2025 | Tasa base de municipios en seguridad | Usar el dato publicado (solo 33 cumplieron) con su cita exacta |
| SINIM, ejecución presupuestaria de inversión municipal | Tasa base por comuna | Confirmar series y cobertura por comuna |
| SEIA, proyectos aprobados frente a construidos | Tasa base de proyectos privados | Confirmar cómo se registra la construcción o caducidad |
| Metro, fechas anunciadas frente a reales | Retraso de grandes obras (segunda iteración) | Reunir fechas con fuente |

## Interfaz con el contrato

`simulacion.json` publica la credibilidad de cada política como `p10`, `media` y `p90`. Son una
**salida** del modelo, calculada a partir de `Beta(α, β)`, no una entrada.
