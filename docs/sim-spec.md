# Spec de simulación: <nombre>

> Plantilla de `sim-scoping`. Completar en la primera hora, antes de escribir el modelo real.
> Ver `docs/simulation-taxonomy.md` para los valores posibles de cada eje.

## Pregunta que responde

"¿Qué pasaría si …?" Debe ser una pregunta cuya respuesta no se conozca de antemano
(la prueba del track: si nadie aprende nada al correrla, es una animación).

## Clasificación (5 ejes)

| Eje | Valor | Consecuencia |
|-----|-------|--------------|
| Tiempo | | |
| Cambio de estado | | |
| Incertidumbre | | |
| Acoplamiento | | |
| Representación | | |

## Paradigma y justificación

DES / Monte Carlo / ABM / CA / mixto. Prueba rápida: si al quitarle la "inteligencia" a las entidades el modelo sigue teniendo sentido, es DES.

## Entidades y variables de estado

## Eventos (DES) o reglas locales (ABM/CA)

| Evento / regla | Cambia el estado | Agenda |
|----------------|------------------|--------|
| | | |

## Parámetros de entrada

| Nombre | Unidad | Valor base | Rango a explorar |
|--------|--------|------------|------------------|
| | | | |

## Métricas de salida

| Nombre | Unidad | Tipo (por observación / ponderada en tiempo / agregada) |
|--------|--------|----------------------------------------------------------|
| | | |

## Validación

- Caso teórico o patrón conocido que el modelo debe reproducir:
- Reproducibilidad (misma semilla, misma trayectoria):
- Casos extremos:

## Experimentos

- Réplicas (mínimo 10, intervalos de confianza):
- Escenarios a comparar (misma semilla por réplica):
- Barrido de parámetros:

## Resultado que esperamos que sorprenda

Qué hallazgo podría contradecir la intuición del equipo.

## Supuestos y simplificaciones

## Stack y estructura del repo

Núcleo en `core/` (sin UI), experimentos en `experiments/`, visualización en `viz/`.
