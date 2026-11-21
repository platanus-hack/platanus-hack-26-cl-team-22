# Viaje Real

Simulador de viajes que responde una pregunta concreta: **¿cuánto ahorras, y cuánta fricción asumes, según las opciones que elijas?**

## El problema

Los planificadores de viaje fallan por dos razones: el sesgo de afiliados (recomiendan eSIMs globales o tours caros) y los promedios estáticos desactualizados. Un viajero puede pagar ~US$4 por 1 GB con una eSIM internacional sin saber que en la ciudad hay chips prepago locales con muchísimo más dato por un precio similar.

## Cómo funciona

- **Dataset pre-indexado** de opciones por ciudad (conectividad, transporte, escapadas, comida, pagos), con fuente y `last_verified_at`. No hay scraping en tiempo real.
- **Motor 100 % determinista**: filtros duros, normalización de unidades (costo por día, costo efectivo por GB) y un `friction_score` de 0 a 100.
- **Restricciones reales**: el tipo de SIM frente al teléfono del viajero (chip físico o eSIM) y los requisitos de identidad (RUT o pasaporte) descartan opciones imposibles de seguir.
- **Tres escenarios en paralelo**: Cero fricción, Balanceado y Optimizado local, con el ahorro en USD y CLP frente al tiempo extra y la fricción.
- **Esquema agnóstico a la ciudad**: Santiago es el seed; agregar una ciudad es agregar datos, no código.

## Auditoría de asistentes de IA

El mismo perfil de viaje se entrega a distintos asistentes de IA y sus recomendaciones se pasan por el motor para medir cuánto sobrepagaría, y cuánta fricción asumiría, un viajero que las siga.

## Estado

MVP en desarrollo. El motor, el repositorio JSON y el seed de Santiago están implementados y con tests. **El dataset de Santiago es un borrador: 10 de 16 opciones tienen fuente y fecha de verificación (en su mayoría guías y comparadores de terceros, que conviene contrastar con la fuente oficial); las otras 6 están marcadas como no verificadas** (`last_verified_at: null`). Cubre conectividad, transporte, escapadas, comida y retiro en cajero; las casas de cambio no se modelan porque su costo es un porcentaje sin cifras confiables. Una interfaz web local y un servidor endurecido ya existen; falta desplegarlos y correr la auditoría contra asistentes de IA reales.
