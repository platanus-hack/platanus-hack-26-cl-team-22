# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Dos usuarios con el mismo peso (confirmado por el equipo el 21 nov 2026):

- **Equipo municipal o regional** que quiere ensayar un plan público antes de aprobarlo: qué pasa si una medida no se cumple, qué pasa si se aprueba un proyecto, a qué otras comunas afecta.
- **Persona que compra vivienda a largo plazo**: hoy puede ver cómo está un barrio, pero no hacia dónde va.

Contexto de uso inmediato: la demo se muestra **proyectada en pantalla grande**, manejada y narrada por alguien del equipo en unos tres minutos, ante el jurado de Platanus Hack 26 Santiago (track Simulations).

## Product Purpose

root simula cómo evolucionan las comunas de la Región Metropolitana de Santiago a 5 y 10 años según los planes públicos que las afectan y la probabilidad real de que se cumplan. Las comunas se afectan entre sí: el aire se mueve por la cuenca y los hogares se mudan entre comunas.

Preguntas que responde: «¿qué pasa si este plan no se cumple?» y «¿qué pasa si se aprueba este proyecto?».

Éxito en la demo: que el jurado vea una simulación con modelo detrás (no una animación), un resultado que sorprende, y la prueba de que el modelo se validó contra datos reales.

## Positioning

- **Credibilidad de ejecución**: cada medida de un plan pesa según el historial real de cumplimiento de quien la ejecuta.
- Políticas extraídas de documentos públicos reales.
- Validación publicada contra datos que el modelo no vio.

No se afirma que «nadie hace esto»: existe UrbanSim para la ubicación de hogares.

## Operating Context

- El modelo corre en Python antes de la demo y escribe `simulacion.json`. La interfaz es una página estática que solo lee ese archivo; no hay servidor ni simulación en el navegador.
- La demo debe funcionar sin red: sin teselas de mapa, sin fuentes ni scripts de CDN.
- Escenarios precalculados: el base y uno por cada política apagada. Una combinación no calculada se dice con palabras.
- Guion de la demo (docs/contexto-proyecto.md §12): problema, mapa con control de tiempo, interruptor de una medida, hallazgo, prueba de validación, perfil de hogar.

## Capabilities and Constraints

- Variable profunda: PM2,5 (invierno, mayo a agosto). Seguridad es secundaria y puede no tener datos. Horizonte: 2026 a 2036.
- **Nunca un número proyectado sin su banda** (p10 a p90). Son proyecciones, no predicciones.
- El interruptor de políticas es la forma de simular; los pesos personales son la forma de leer el resultado.
- Solo se dibuja lo que viene del modelo: nada de animaciones decorativas de viento o partículas sin datos.
- Mientras el archivo sea de ejemplo (`meta.es_ejemplo`), la etiqueta «Datos de ejemplo» está siempre visible.
- Comunas con polígono pero sin dato se muestran como «sin dato», no se ocultan.
- Sin inmigración ni nacionalidad como variable.
- Solo escritorio. Tamaños de referencia: 1440×900 y 1280×720.
- Texto de la interfaz en español; números con coma decimal.
- Hallazgo candidato para la demo (modelo de tamizaje, magnitud sin confirmar): el plan prohíbe la leña en la Zona A, pero el 77 % de las emisiones de leña está en la Zona B.

## Brand Commitments

- Nombre del producto: **root** (escrito así por el equipo; mayúscula inicial sin confirmar). No hay logo ni identidad visual definidos.
- El equipo rechaza el aspecto genérico de producto hecho con IA: nada de neón, degradados morados o azules, vidrio esmerilado, brillos ni emojis.

## Evidence on Hand

- Mediciones reales de PM2,5 por estación, 2017 a 2024 (`data/aire/`).
- Emisiones por comuna y fuente del RETC, 2023 (`data/emisiones/`).
- Polígonos oficiales de las 52 comunas (`viz/public/geo/comunas_rm.geojson`).
- Inventario de políticas del plan de descontaminación (`docs/politicas-aire.md`).
- `viz/ejemplo/simulacion.json` es **ejemplo**: solo su línea base es real.
- Todavía no existen: resultados del modelo real, cifras de validación, datos de seguridad. No se deben inventar.

## Product Principles

1. La incertidumbre es parte del resultado y siempre se muestra.
2. Cada elemento en pantalla sale del modelo o de un dato con fuente.
3. Las interacciones entre comunas son el argumento: deben verse.
4. Un resultado negativo bien medido se dice.
5. La explicación acompaña al número: qué política lo mueve y con qué credibilidad.
