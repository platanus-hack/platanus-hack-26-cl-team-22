# Opciones de transformación dinámica del mapa

**Recomendación:** combinar **Opción A (coropleta y bandas con interpolación continua entre años)** con **Opción B (focos y halos solo sobre comunas con cambio real)**, alimentadas por la nueva clave `transformaciones` de `viz/datos/simulacion.json` y las primitivas puras de `viz/src/lib/transicion.ts`. Mantiene rigor científico (`PRODUCT.md`: cero partículas decorativas sin dato), funciona tanto en el mapa 3D (`MapaRelieve.tsx`) como en el respaldo SVG (`MapaPapel.tsx`) y respeta `prefers-reduced-motion`.

> **Alcance actual:** el motor ya precalcula `transformaciones` en `simulacion.json` y `viz/src/lib/transicion.ts` expone el contrato y las funciones puras probadas, con `modo: 'ninguno'` por defecto para no alterar todavía la interfaz visual.

## Opciones evaluadas

| Opción | Qué transforma en el mapa | Qué dato del modelo la respalda | Paridad 3D (`MapaRelieve`) / SVG (`MapaPapel`) | Riesgo frente a `PRODUCT.md` | Recomendación |
|---|---|---|---|---|---|
| **A. Coropleta + banda continua** | Interpola `(p10, p50, p90)` entre año `t` y `t+1` al reproducir la línea de tiempo (`interpolarMapaPuntos`) | `trayectorias[escenario][comuna][variable]` | Alta: `MapaRelieve` ya interpola RGB a 320 ms; SVG puede actualizar relleno/festón | Ninguno si las bandas se interpolan respetando `p10 ≤ p50 ≤ p90` | **Implementar primero** |
| **B. Focos y halos en comunas activas** | Pulsa o resalta borde/halo proporcional a `intensidad` en las comunas que más cambian (`comunas_foco`) | `transformaciones.por_escenario[esc].comunas_foco` (`delta_p50`, `incertidumbre`, `intensidad`) | Alta: capa `circle`/`line` desde `featuresDeFocos()` en MapLibre y anillo SVG en `MapaPapel` | Bajo: el radio/opacidad es estrictamente proporcional a `intensidad` e `incertidumbre` | **Implementar junto con A** |
| **C. Encuadre guiado al epicentro / bbox** | Desplaza suavemente la cámara hacia la zona donde ocurre la transformación al cambiar escenario (`easeTo` / `interpolarVista`) | `epicentro { lat, lon }` y `bbox [lonMin, latMin, lonMax, maxLat]` ponderados por la `intensidad` de cada foco | Alta: `fitBounds`/`easeTo` en MapLibre y `ajustarCaja` + `interpolarVista` en SVG | Medio si mueve la cámara sin acción explícita del usuario; mejor ofrecerlo como botón o vista | **Fase 2 (opcional con toggle)** |
| **D. Progresión en flujos / cintas de acoplamiento** | Ajusta grosor/opacidad de las cintas año a año según el escenario activo (`cintas` y `flujos`) | `origen_aire` (fracción emisora) y `flujos` (mudanzas por año) | Media: en 3D son `LineString` GeoJSON; en SVG ya existen rutas cuadráticas `rutaCurva` | Alto si simula partículas móviles falsas; aceptable si solo modula grosor o trazo continuo | **Solo modular grosor sin partículas** |
| **E. Extrusión / alzado 3D en modo diferencia** | Eleva cada comuna proporcionalmente a `\|delta_p50\|` en «El plan» (`fill-extrusion-height`) | `delta_p50` de `comunas_foco` en `transformaciones` | **Baja:** solo existe en WebGL/MapLibre (`MapaRelieve`); el SVG plano queda en 2D | Medio: puede tapar comunas vecinas o etiquetas con `pitch = 60` | **Descartada para MVP** |

## Dónde viven las bases ya montadas

| Pieza | Archivo | Qué aporta |
|---|---|---|
| Cálculo pareado por escenario | `core/transformaciones.py` | Calcula `delta_p50`, `incertidumbre` (`q90 - q10`), `intensidad` normalizada en `[0, 1]`, `direccion` (`mejora` / `empeora` / `neutro`), `epicentro` y `bbox` |
| Serialización en JSON | `experiments/simular.py` | Emite `simulacion.json["transformaciones"]` para los 12 escenarios sin recalcular réplicas |
| Contrato tipado y validación | `viz/src/lib/types.ts`, `viz/src/lib/validate.ts` | Interfaces `TransformacionesMapa`, `TransformacionEscenario` y parser defensivo `leerTransformaciones` |
| Primitivas puras de transición | `viz/src/lib/transicion.ts` | Curvas (`lineal`, `easeOutCubic`, `easeOutExpo`), `resolverProgreso` (respeta `reducido`), `cursorDeProgreso`, `interpolarMapaPuntos`, `estadoTransformacionEnCursor`, `comunasMasTransformadas` y `featuresDeFocos` |
| Gancho en componente mapa | `viz/src/components/MapaPapel.tsx` | Prop opcional `transicion?: EstadoTransicionMapa` en `PropsMapa` (sin efecto visual todavía) |

## Reglas para mantener coherencia con el proyecto

1. **Sin animaciones decorativas (`PRODUCT.md`):** no agregar viento inventado ni partículas sin respaldo en `trayectorias` o `transformaciones`.
2. **Accesibilidad (`prefers-reduced-motion`):** toda transición debe pasar por `resolverProgreso(t, reducido, curva)` para saltar de inmediato a `1` cuando el usuario prefiere movimiento reducido.
3. **Solo donde el patrón está validado:** para el PM2,5, `make validate` muestra que repartir el mismo cambio en todas las comunas predice igual que el modelo. Por eso esos escenarios traen `comunas_foco` vacío, epicentro y `bbox` de toda la región, y un `aviso`; las Opciones B y C aplican hoy solo a seguridad.
4. **Incertidumbre visible:** en Opción B, acompañar la `intensidad` del foco con su `incertidumbre` (por ejemplo, ancho del trazo o lectura en la ficha), nunca ocultar la banda.
5. **Cero lógica de modelo en el render:** `App.tsx`, `MapaRelieve.tsx` y `MapaPapel.tsx` solo consumen `estadoTransformacionEnCursor(...)` y `interpolarMapaPuntos(...)`.

## Cómo conectar la animación cuando el equipo la active

```ts
const cursor = cursorDeProgreso(progresoAnio, data.meta.anios.length)
const transicion = estadoTransformacionEnCursor(
  data.transformaciones?.por_escenario[escenario.id],
  cursor,
  { modo: 'focos', reducido, umbralFoco: 0.15 },
)
const focosGeo = featuresDeFocos(transicion, centrosPorComuna)
```

- Con `modo: 'ninguno'` (valor por defecto), `transicion.activo` es `false` y el mapa conserva exactamente su comportamiento actual.
- Al activar `'coropleta_continua'` o `'focos'` en un `requestAnimationFrame` en `App.tsx`, la interpolación y los puntos GeoJSON salen listos sin recalcular nada sobre el DOM.

## Checklist antes de animar en UI

- [ ] Verificar que `viz/datos/simulacion.json` incluye `transformaciones.por_escenario` para todos los escenarios activos.
- [ ] Pasar `transicion` desde `Simulador` (`viz/src/App.tsx`) hacia `Mapa` → `MapaRelieve` / `MapaPapel`.
- [ ] Agregar una capa de foco discreta (`circle` o borde) en `estiloRelieve()` y su equivalente SVG en `MapaPapel.tsx`.
- [ ] Comprobar con `prefers-reduced-motion: reduce` que al cambiar año o escenario la transición termina en un cuadro (`resolverProgreso === 1`).
