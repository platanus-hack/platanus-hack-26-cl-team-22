# Contexto del proyecto · Simulador de comunas por políticas públicas

Platanus Hack 26 · final en Santiago · team-22 · **track Simulación** · 36 horas de ejecución
Actualizado: 21 nov 2026

> Este archivo es el contexto base para cualquier sesión de desarrollo del MVP. Si algo aquí contradice una instrucción puntual del equipo, manda la instrucción del equipo.
> Para la arquitectura, los frentes de trabajo y el contrato `simulacion.json`, ver [`plan-comunas.md`](./plan-comunas.md).

---

## 1. Qué construimos

Un simulador que proyecta cómo evolucionan las comunas de la Región Metropolitana a 5 y 10 años según los **planes públicos que las afectan** y la **probabilidad real de que se cumplan**. Las comunas se afectan entre sí: el aire se mueve por la cuenca, los hogares se mudan entre comunas y la seguridad tiene efectos sobre las vecinas.

Pregunta central de la demo: **«¿qué pasa si este plan no se cumple?»** y **«¿qué pasa si se aprueba este proyecto?»**.

Lo más original del proyecto es la **credibilidad de ejecución**: cada medida de un plan pesa según el historial de cumplimiento de quien la ejecuta.

## 2. Cómo nos evalúan

| Criterio | Peso | Qué buscan |
|---|---|---|
| Aspecto técnico | 25 % | Un **agente lee el repositorio**. Arquitectura sólida, baja trivialidad, integración real (no un wrapper de API) |
| Ambición | 20 % | Ideas grandes que no sea obvio lograr en 36 h |
| Ejecución | 20 % | Avance real, lo que funciona en la demo |
| Impacto | 20 % | Efecto tangible y a gran escala |
| Originalidad | 15 % | Algo que los jueces no hayan visto |

Restricciones del equipo: nada de videojuegos, chats, pizarras ni tableros Kanban. El negocio no se evalúa.

**Lo que el track descalifica** (según las observaciones del equipo; falta confirmar el texto oficial): una proyección que sale de una fórmula o planilla, o una visualización bonita sin modelo detrás. Por eso las comunas **tienen que interactuar** y el resultado tiene que poder sorprender.

## 3. Estado de las decisiones

### Decidido

- Track Simulación (no Multiplayer).
- Variables: **aire (PM2,5) como variable profunda**, **seguridad como secundaria**, población como puente.
- Fuera del MVP: colegios, salud, transporte, precios y plusvalía, otras regiones, conexión con First Street.
- Horizonte: **5 y 10 años** como resultado; 30 años solo como escenario exploratorio, rotulado así.
- Catálogo cerrado de intervenciones con rangos de efecto citados. **El LLM clasifica, nunca escribe números.**
- Validación separada (ajuste ≠ prueba) y comparada contra alternativas simples.
- Sin inmigración como variable de riesgo.
- Pesos personales sí, pero sin fricción (ver sección 8).

### Abierto (con recomendación)

| Decisión | Opciones | Recomendación |
|---|---|---|
| Shock de la demo | Venezuela → migración / algo fechado y medible (línea de Metro, proyecto aprobado en el SEIA) | Fechado y medible. Venezuela queda como extensión |
| Hogares | Flujos agregados entre comunas / miles de agentes sintéticos | Flujos agregados, calibrados con los censos |
| Usuario al centro del pitch | Municipio / comprador de vivienda | Municipio primero; comprador como cara humana |
| Métrica de impacto | Personas expuestas sobre la norma de MP2,5 / costo en salud / viviendas afectadas | Personas expuestas sobre la norma |
| Comunas en la demo | — | Todas en el modelo (las interacciones lo necesitan); 5–6 destacadas en la interfaz |

## 4. El modelo

### Ciclo de un año simulado

1. Se sortea qué medidas de cada plan se ejecutan ese año, según la **credibilidad por medida**.
2. Las medidas ejecutadas cambian emisiones y delitos en su comuna.
3. El aire se reparte por la cuenca; la seguridad tiene un efecto sobre las comunas vecinas.
4. Los hogares comparan comunas y una parte se muda.
5. La población nueva cambia las emisiones del año siguiente.

El ciclo se repite cientos de veces por escenario (Monte Carlo) y de ahí salen **bandas de incertidumbre**, nunca un número único.

### Mecanismos y orden de construcción

| Orden | Mecanismo | Qué simula | Cuidado clave |
|---|---|---|---|
| 1 | **Aire** | Emisiones por fuente (calefacción, transporte, industria) → concentración por comuna, acoplada por la cuenca | Solo hay ~11 estaciones MACAM para 52 comunas: el método de estimación por comuna tiene que quedar escrito |
| 2 | **Hogares** | Flujos de mudanza entre comunas | Inercia (la mayoría no se muda) y tope de viviendas por comuna. Si solo aire y seguridad mueven hogares, el modelo exagera las mudanzas |
| 3 | **Seguridad** | Tasa de delitos con inercia + efecto de cada intervención del catálogo | Efecto sobre vecinas con **signo abierto**: la evidencia muestra que la difusión de beneficios es al menos tan común como el desplazamiento. Es lo primero que se recorta si falta tiempo |

### Reglas del modelo

- **La población solo afecta lo físico**: emisiones, demanda y carga sobre servicios. **No** entra a la seguridad.
- **Credibilidad por medida**, no por plan. Plan de descontaminación: historial desde los informes de avance de la SMA. Planes comunales de seguridad sin historial: credibilidad baja y banda ancha.
- **Atribución**: el aporte de una política = simulación con la política − simulación sin ella.
- **Velocidad**: la simulación se precalcula por escenario; los pesos solo reordenan resultados ya calculados.
- **Años atípicos**: 2019 (estallido), 2020 y 2021 (pandemia) se marcan para no atribuir sus cambios a los planes.

### Catálogo de intervenciones

| Variable | De dónde sale el efecto | Solidez |
|---|---|---|
| Aire | Metas de reducción de emisiones del propio plan de descontaminación, por fuente | Alta |
| Seguridad | Metaanálisis: cámaras (Piza et al., 2019: baja significativa y modesta, mayor en estacionamientos) e iluminación (Welsh, Farrington y Douglas, 2022) | Media. Ningún estudio es chileno: **bandas anchas** |

Lo que no calza en ningún tipo del catálogo queda fuera y se informa.

## 5. Datos

| Qué | Fuente | Notas |
|---|---|---|
| PM2,5 | SINCA (red MACAM) | **No tiene API pública documentada.** Usar la librería `atmchile` (endpoints obtenidos por ingeniería inversa). **Descargar y cachear antes**; guardar fecha de descarga |
| Delitos por comuna | CEAD (Subsecretaría de Prevención del Delito) | Serie anual por comuna |
| Victimización comunal | ENUSC, estimación de áreas pequeñas del INE | Estadística experimental |
| Población y viviendas | Censo 2017 y Censo 2024 (microdatos por comuna, CSV/parquet) | RM: 7.400.741 personas, 2.764.749 viviendas (2024) |
| Mudanzas entre comunas | Pregunta «comuna de residencia hace 5 años» de ambos censos | Dos matrices: 2012→2017 y 2019→2024. Una para ajustar, otra para probar |
| Plan de aire | PPDA RM (D.S. 31/2016, vigente desde 24-nov-2017) + informes de avance de la SMA | Experimento natural para la validación. **Pendiente**: confirmar que la SMA reporta cumplimiento medida por medida |
| Planes de seguridad | Planes Comunales de Seguridad Pública (Ley 20.965), PDFs municipales | Contraloría: 312 municipios no remitieron documentación 2024–2025; solo 33 cumplieron |
| Proyectos nuevos | SEIA | Región, sector, inversión |

## 6. Validación

| Pregunta del juez | Qué hacemos | Qué mostramos |
|---|---|---|
| ¿Lo ajustaron con los mismos datos con que lo prueban? | **Aire**: validar con datos mensuales (SINCA mide por hora). **Seguridad**: dejar comunas completas fuera del ajuste. **Hogares**: ajustar con la matriz 2012→2017 y probar con 2019→2024 | El error solo sobre datos que el modelo nunca vio |
| ¿Es mejor que no hacer nada? | Comparar contra «todo sigue igual» y «sigue la tendencia» | Cuánto gana el modelo, por variable |
| ¿Las bandas significan algo? | Contar cuántos valores reales caen dentro de la banda del 80 % | Si es cerca del 80 %, las bandas son honestas |

**Si el modelo no le gana a la tendencia simple, se dice.** Un resultado negativo bien medido vale más que un acierto inexplicable.

## 7. Impacto

- **Métrica central (recomendada)**: personas expuestas sobre la norma de MP2,5 = concentración simulada por comuna × población del censo.
- **No** calcular muertes evitadas en el MVP (exige función dosis-respuesta; queda como extensión).
- Escala de contexto: el MMA estima ~4.000 muertes prematuras/año por contaminación del aire (Lancet Countdown 2024: ~4.500); costo en salud del MP2,5 ~US$5.000 millones/año.
- Usuarios: municipios que ensayan su plan antes de aprobarlo → fiscalización y ciudadanía (el incumplimiento como cifra) → comprador de vivienda.

## 8. Pesos personales sin fricción

1. **Simular una vez, ponderar al instante**: mover un peso reordena resultados precalculados en el navegador.
2. **Pocos controles**: máximo tres pesos (aire, seguridad, crecimiento de población).
3. **Perfiles de partida**: por ejemplo «sensible a la contaminación», «prioriza seguridad».
4. **Cada cambio se explica**: qué comuna subió o bajó y por qué.
5. **Sin pasos previos**: nada de registro ni configuración para la demo.

Los pesos son la forma de **leer** la simulación; el interruptor de políticas es la forma de **simularla**. El interruptor va al centro de la interfaz.

## 9. Lo que no hacemos

- Usar nacionalidad o inmigración como variable de riesgo (la evidencia chilena no la respalda y sería discriminación residencial).
- Dejar que el LLM invente rangos de efecto.
- Prometer un número exacto o proyecciones a 30 años como resultado.
- Asumir que el delito siempre se desplaza a la comuna vecina.
- Afirmar que «nadie hace esto»: existe UrbanSim (microsimulación de ubicación de hogares). Nuestro diferencial: credibilidad de ejecución, políticas extraídas de documentos reales, orientación ciudadana y validación publicada.

## 10. Lo que el agente juez debe encontrar en el repo

- Un documento del modelo: cada mecanismo, sus ecuaciones y el origen de cada parámetro.
- El catálogo de intervenciones con la cita de cada rango.
- Resultados de validación guardados, con el comando que los reproduce.
- Semillas fijas, separadas por fuente de azar.
- Pruebas automáticas del núcleo, por ejemplo: la población total se conserva al mudarse; una política con credibilidad 0 no tiene efecto.
- Origen y fecha de descarga de cada fuente de datos.
- Núcleo del modelo separado de la interfaz.

## 11. Reparto del trabajo

| Sesión | Qué construye | Entrega |
|---|---|---|
| Datos de aire | Descarga de SINCA y estimación por comuna | Serie de PM2,5 por comuna, 2017–2024 (mensual) |
| Datos de seguridad y población | CEAD, ENUSC y censos alineados por comuna | Series anuales + matrices de mudanza |
| Extractor de políticas | PDFs clasificados en el catálogo | Medidas con tipo, comuna, año y credibilidad |
| Núcleo de simulación | Mecanismos y ciclo anual | Motor: escenario → trayectorias |
| Validación | Ajuste, prueba, alternativas simples | Informe de error y gráficos |
| Interfaz | Mapa, control de tiempo, interruptores, pesos | Pantalla de la demo |

**Primero el núcleo y los datos de aire**: todo depende de ellos.

## 12. Demo de tres minutos

1. **Problema**: «Hoy puedes ver cómo está un barrio. Nadie te muestra hacia dónde va».
2. **Mapa**: la RM con control de tiempo, 2026 → 2036.
3. **Interruptor**: se apaga una medida del plan de descontaminación y se ve qué comunas empeoran, incluidas las que no la ejecutaban.
4. **Hallazgo**: el resultado que no esperábamos, con su explicación.
5. **Prueba**: modelo contra realidad contra tendencia simple.
6. **Usuario**: un perfil elige prioridades y el ranking se reordena al instante.

## 13. Pendientes por verificar

- [ ] Texto oficial del track Simulación y del criterio de impacto.
- [ ] Número actual de estaciones MACAM y años completos de cada una.
- [ ] Si los informes de la SMA traen cumplimiento medida por medida.
- [ ] Rangos de efecto para patrullaje focalizado y aplicabilidad a Chile.

## 14. Documentos del proyecto

- Whitepaper v1: https://claude.ai/artifact/4WiDC7yncYA8uzrBeHvGGi
- Iteración del modelo (respuesta a observaciones): https://claude.ai/artifact/DWRbFzNJdtW4WPv3nUkXhq
- Impacto: https://claude.ai/artifact/UrUuRcxEJVhgQgkWLJHxjD
- Whiteboard (versión inicial, todavía dice Multiplayer): https://claude.ai/artifact/He8je28J627DCvTvNMh82f
