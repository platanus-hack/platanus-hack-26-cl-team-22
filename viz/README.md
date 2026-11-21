# viz/

Visualización de la simulación. Reglas:

- Lee el estado del núcleo (`core/`) o los CSV de `results/`; **nunca los modifica**.
- Sin lógica de modelo dentro del bucle de render.
- Si es web: TypeScript + Canvas, simulación en un Web Worker, PRNG con semilla (nunca `Math.random()`).
- Si es Python: cualquier librería, siempre separada de `core/`.

Decidir el stack en el kickoff (ver `.claude/skills/sim-scoping`, Paso 4).

## Interfaz (Frente 8): root, «Capas de papel»

Página estática de una sola pantalla: Vite + React + TypeScript (strict). Los datos son archivos propios
(`datos/*.json`, `geo/comunas_rm.geojson`); no hay backend ni analítica. La tipografía (Bricolage Grotesque)
viene empaquetada con `@fontsource`.

### El mapa: relieve en 3D con dos respaldos

El mapa es la cuenca en relieve (MapLibre GL JS 6.19.0, código abierto): la cordillera, las calles y las comunas
pintadas encima con el color de su nivel. `src/components/Mapa.tsx` elige solo cuál usar, en este orden:

| Mapa | De dónde sale | Cuándo se usa |
|---|---|---|
| Relieve en línea | Calles de OpenFreeMap y relieve de Mapterhorn (gratis, sin clave) | Siempre que haya internet |
| Relieve local | Paquete predescargado en `viz/public/mapas/` (`npm run mapas`, unos 67 MB, fuera de git) | Si el estilo en línea no responde en 4 s |
| Plano («Capas de papel») | SVG propio, sin teselas ni red (`MapaPapel.tsx`) | Si no hay red ni paquete, o si WebGL falla |

- **Antes de presentar:** correr `npm run mapas` una vez con internet. Se puede repetir; salta lo ya bajado.
- **Forzar un respaldo:** abrir con `?mapa=local` o `?mapa=plano`, o apretar `L` en plena presentación
  (en línea → local → plano).
- El paquete local cubre la Región Metropolitana hasta el zoom 12 (sin edificios en 3D, que solo vienen en línea).
- Las únicas peticiones externas son las teselas del mapa en línea; no se envía ningún dato de la pantalla.
- En el relieve, la banda p10–p90 que alcanza otro nivel se marca con una trama; el festón y las hojas de política
  de la comuna elegida solo existen en el mapa plano. Las comunas del relieve se eligen con clic (el recorrido con
  `Tab` es del mapa plano).

Cada política es una hoja de papel frío pegada bajo las comunas donde aporta: asoma por el canto de abajo a la
derecha, más ancha cuanto más aporta, y varias se apilan en orden. Apagar una política la desliza fuera de la pila
y el papel cálido del nivel cambia en el mismo gesto. Un borde festoneado marca la incertidumbre.

### La hoja Riesgo: una dimensión o una variable en detalle

La primera hoja tiene un selector que manda sobre el panel y sobre el mapa:

| Capa | Qué muestra el panel | Qué pinta el mapa |
|---|---|---|
| General | El índice de riesgo de la comuna (0 a 100), su veredicto, las tres de menor riesgo y una fila por variable | El índice |
| Aire | Valor, veredicto frente a la norma anual, proyección con banda y la política que más lo mueve | PM2,5 frente a la norma |
| Seguridad, Crecimiento | Valor, veredicto por posición y proyección con banda | La posición de riesgo en esa variable |

**Unidad del índice** (`src/lib/riesgo.ts`): en cada variable, el riesgo de una comuna es el porcentaje de las
otras comunas que están mejor que ella en ese año (0 = la mejor, 100 = la peor). El índice general es el promedio
de esos riesgos, ponderado por la prioridad de 0 a 10 que se le da a cada variable (los perfiles de
`tipos_hogar` son prioridades ya puestas). Hasta 33 es riesgo bajo; hasta 66, medio; más, alto. Se usa la
posición y no el valor porque las unidades son distintas y hay comunas muy alejadas del resto.
Es un índice relativo a la región: no dice si el valor es bueno en términos absolutos; para el aire, eso lo dice
la norma, y por eso la fila de aire marca «Sobre la norma» aunque la posición sea buena.

### Entrada guiada

Al abrir, dos pantallas sobre el mapa (`src/components/Onboarding.tsx`):

1. **El caso, en texto libre.** `leerCaso` (`src/lib/onboarding.ts`) lo clasifica por palabras clave en energía
   hidráulica, vivienda, industria o evaluación general; la persona ve cómo se leyó y puede cambiarlo.
2. **Los criterios.** Los tres que simula el modelo llevan peso (cinco grados) y un rango aceptado: para el aire,
   la norma chilena o las metas de la OMS; para seguridad y crecimiento, cortes sobre los datos de la región.
   Debajo van los criterios propios de ese caso (caudal, caída, etc.) y los que agregue la persona: **no tienen
   datos en esta versión, no entran al cálculo y no muestran ningún número**.

Al terminar se abre la hoja Riesgo: las tres de menor riesgo salen solo de las comunas que cumplen todos los
rangos, y la ficha marca «Fuera de tu rango» donde corresponde. Con `?directo` en la dirección no aparece.

La explicación la arma la propia interfaz con los números del índice (`src/lib/onboarding.ts`). Si al construir
se define `VITE_GUIA_URL` con la dirección de un intermediario propio y la persona escribió su caso, se le pide
a ese intermediario un texto redactado por un modelo de lenguaje (`src/lib/guia.ts`):

- Pedido: `POST` con JSON `{ perfil, contexto, prioridades, anio, top, falta }`; `top` trae las tres comunas de
  menor riesgo con sus valores. Respuesta: JSON `{ "texto": "..." }`.
- La clave del modelo vive en el intermediario, nunca en esta página. El intermediario debe permitir el origen
  de la página (CORS) y limitar el uso.
- El modelo solo redacta: el orden de las comunas lo calcula siempre el índice. Si el intermediario no está,
  tarda más de 12 s o responde otra cosa, queda la explicación propia.
- Lo que escribe la persona sale de la página solo en ese pedido; sin `VITE_GUIA_URL` no sale nunca.

### Junto a la landing

`web/` (la landing) y `viz/` se publican como un solo sitio: `npm run build` en `web/` construye la landing,
construye esta interfaz con `VITE_INICIO_URL=../` y la copia a `web/dist/simulador`
(`web/scripts/incluir-simulador.mjs`). En la landing, al terminar el scroll queda la introducción con el botón «Entrar al simulador» (o un gesto nuevo de seguir bajando): el globo vuela hacia la región y se
abre `simulador/`; aquí, la marca «root» vuelve a la landing. Para probar el paso en desarrollo, correr esta
interfaz con `npm run dev -- --port 5174` y la landing con `npm run dev` (su `.env.development` apunta a ese puerto).

### Cómo correrla

```bash
cd viz
npm install
npm run dev        # http://localhost:5173
npm run typecheck  # tsc --noEmit
npm test           # Vitest: lógica pura (escenarios, niveles, proyección, festones, capas, leña, teclas, validador…)
npm run mapas      # baja el paquete de mapas para presentar sin internet (viz/public/mapas)
npm run build      # genera viz/dist, estática, con rutas relativas
npm run preview    # sirve viz/dist
```

Pensada para escritorio 16:9 y 16:10 (1920×1080, 1440×900, 1280×720), sin desplazar la página.

### Teclado

| Tecla | Qué hace |
|---|---|
| `1` … `3` (`4`, `5`) | Vistas: Riesgo, El plan, La leña y, si el archivo trae `validacion`, La prueba; si existe `datos/demografia.json`, Las mudanzas |
| `Q` `W` `E` `R` … | Enciende o apaga el plan de esa fila en El plan (la letra está impresa en cada fila) |
| `←` `→` | Año anterior o siguiente |
| `Espacio` | Reproduce o pausa los años |
| `D` | En El plan, alterna el mapa entre valor y diferencia frente al escenario de referencia |
| `M` | Alterna Gran Santiago y toda la región |
| `0` | Reencuadra |
| `L` | Cambia de mapa: relieve en línea, relieve local, plano |
| `Esc` | Pausa |
| `Tab` + `Enter` | Recorre las comunas del mapa y elige una |

Sin uso durante 45 s, la pantalla se demuestra sola (recorre años y vistas y despega y vuelve a pegar una
política) con la etiqueta «Demostración automática». Cualquier tecla, clic o movimiento la detiene.
Con `prefers-reduced-motion` los cambios son instantáneos.

### Dónde van los datos

| Archivo | Quién lo pone | Qué pasa si falta |
|---|---|---|
| `viz/datos/simulacion.json` (lo sirve y empaqueta `vite.config.ts` como `datos/simulacion.json`) | El modelo: `python -m experiments.simular` | Se usa `viz/ejemplo/simulacion.json` (se sirve como `datos/ejemplo.json` por un plugin de `vite.config.ts`) y aparece «Datos de ejemplo» si `meta.es_ejemplo` es true |
| `viz/public/datos/lena.json` | `datos/viz/build_lena.py` | La vista La leña lo dice en palabras |
| `viz/public/datos/demografia.json` | `python -m experiments.exportar_demografia` | La vista Las mudanzas no aparece. Es la simulación por agentes de `docs/modelo-mudanzas-abm.md`: corre en un Web Worker (`src/lib/abm.worker.ts`), 20 corridas por cambio, y el mapa pinta la ocupación de la vivienda |
| `viz/public/geo/comunas_rm.geojson` | Frente de cartografía | Cada comuna se dibuja como un círculo en su lat/lon |

Si el JSON no cumple el contrato (`docs/plan-comunas.md`), la página muestra un estado de error con la
lista de problemas. Son opcionales y su sección simplemente no aparece si faltan: `flujos`, `aportes`,
`origen_aire`, `impacto`, `validacion`, `promesas` (hoy no se muestra) y la variable `seguridad`.
`origen_aire` mal formado (fracción fuera de 0 a 1, suma mayor que 1) rechaza el archivo con un mensaje claro.
La variable del mapa sale de `variables[]`; las lecturas de credibilidad (`escenarios[].lectura`,
`meta.lecturas`) se ofrecen en El plan; el escenario se elige por coincidencia exacta de políticas activas y lectura.

### Regenerar `lena.json`

```bash
.venv/Scripts/python -I datos/viz/build_lena.py
```

Lee `data/emisiones/pm25_por_comuna_fuente.csv` (año 2023, fuente `lena`) y `data/comunas_rm.csv`, asigna la
Zona A o B según el art. 73 del D.S. 31/2016 (`docs/politicas-aire.md`) e imprime la parte de la Zona B
(hoy 77,3 %: 2.487 de 3.218 t). Una comuna sin fila queda «sin dato» (nunca cero). Si la simulación trae
`comunas[].zona_ppda`, la interfaz usa esa zona y avisa en la consola si difiere.

### Estilo

Todo color, tamaño y tiempo está en `src/tokens.css`: papeles de nivel `--nivel-0..5` (cálidos), de política
`--pol-0..4` (fríos), de diferencia `--mejora-1..3` y `--empeora-1..3`, zonas `--zona-a`, `--zona-b`. Los cortes
de nivel viven en `src/lib/niveles.ts` (referencia provisional, pendiente del equipo): para medias anuales, seis
pasos relativos a la norma anual N (`impacto.norma_ugm3`, o 20): hasta 0,5 N, 0,75 N, N, 1,15 N, 1,3 N y más
(10/15/20/23/26 con N = 20); para invierno, cinco pasos en 20/30/40/50 µg/m³.

### Estructura

```
src/lib/        lógica pura y sus tests: validate, load, scenario, scoring, findings, geo, format, data, vista,
                diferencia, origen, niveles, proyeccion, feston, capas, lena, interaccion
src/components/ MapaPapel (mapa SVG), Vistas (las cinco hojas), TiraPolitica, GraficoBanda, Papel (rodela,
                muestras, icono), Marco (leyenda, encuadre, años)
src/App.tsx     estado, teclado y demostración;  src/main.tsx  carga de datos y estados de error
```
