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
| Relieve local | Paquete predescargado en `viz/public/mapas/` (`npm run mapas`, unos 67 MB, fuera de git) | Si el estilo en línea no responde en dos intentos de 8 s |
| Plano («Capas de papel») | SVG propio, sin teselas ni red (`MapaPapel.tsx`) | Si no hay red ni paquete, o si WebGL falla |

- **Una red lenta no cambia de mapa:** el relieve se queda y pinta las teselas a medida que llegan. Solo se
  pasa al respaldo si el estilo no carga (sin red) o si WebGL no arranca.
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

### Pestañas por tipo de riesgo

Cinco pestañas (`src/lib/pestanas.ts`); todas menos el resumen abren con un título y un subtítulo, y las que
tienen varias secciones las muestran como acordeón con una sola abierta, que también manda sobre el mapa:

| Pestaña | Secciones | Qué pinta el mapa |
|---|---|---|
| Resumen | El índice de riesgo de 0 a 100, las tres de menor riesgo y una fila por variable que pesa | El índice |
| Climático | Calidad del aire · La leña, su fuente principal · El agua: caudal de los ríos | PM2,5 frente a la norma · zonas y emisiones de leña · ríos y estaciones de caudal |
| Legal | Los planes públicos, su probabilidad de cumplirse y el efecto de encender o apagar cada uno | Valor o diferencia |
| Social | Seguridad ciudadana · Crecimiento poblacional · Desarrollo urbano (la simulación de mudanzas) | Posición de riesgo · flujos |
| Referencias | Fuentes de datos y normas · El modelo contra datos que no vio | Sin cambio |

En el resumen, cada fila de variable lleva a su pestaña y sección.

**El agua** (`src/lib/agua.ts`, `src/components/VistaAgua.tsx`): caudal medio mensual medido por las estaciones
de la DGA entre 1980 y 2017. Es medición histórica, no sale del modelo y no cambia con el año de la simulación.
Todo reacciona al **estado del caudal**: el de lo que se mira dividido por lo normal de esa estación (su
promedio 1980–2009). Con 85 % o más es normal (azul); entre 60 y 85 %, bajo (naranja); con menos, crítico
(rojo). Ese color lo llevan el río, el punto de su estación, la cifra y cada barra de la serie. El mapa dibuja
cada cauce con un ancho que crece con la raíz de su caudal y un brillo que corre aguas abajo y se apaga cuando
el caudal es crítico; cada punto es una estación de la DGA y **late solo si su caudal está en nivel crítico**
(la leyenda lo dice). Se puede mirar la megasequía 2010–2017 (lo primero que se ve), el promedio 1980–2017 o
un año, y «Ver año por año» los recorre. La hoja muestra además el régimen (de deshielo o de lluvia, por el
mes de más agua) y la variabilidad. En el mapa en relieve los ríos con nombre salen de `geo/rios_rm.geojson` y no de las teselas del mapa base,
que a algunos niveles de zoom traen esos cauces sin nombre; la red fina de fondo sí es la de las teselas. Ancho,
color y elegido son estado de cada tramo y de cada estación (`setFeatureState`), y las capas del agua se
ocultan por opacidad: sobre el terreno, ocultar una capa o vaciar su fuente deja restos dibujados.
Un cauce sin estación se dibuja fino y no cambia. Elegir una comuna pasa a su estación de más caudal, si
tiene. Cada río con nombre trae las comunas por donde pasa, de aguas arriba a aguas abajo (`cauces` en
`caudales.json`): la hoja las muestra en fila y el mapa las tiñe. En el perfil «Energía» el resumen ofrece un botón directo a esta sección. El caudal no entra
al índice de riesgo: solo 14 estaciones cumplen el filtro y no hay un valor por comuna.

**«¿Y si sigue la megasequía?»** (`src/lib/aguaSim.ts`): la parte del agua que sí es simulación. Para cada
escenario se sortean 500 décadas posibles de 2026 a 2036 por remuestreo en bloques de tres años seguidos de
los años medidos: «Sigue la megasequía» sortea de 2010–2017, «Todo el registro» de 1980–2017 y «Vuelve lo
normal» de 1980–2009. Los bloques conservan que a un año seco suele seguirle otro, y el mismo año real se usa
en todas las estaciones de una década, así un año seco lo es en toda la cuenca. La hoja muestra una década
concreta (se reproduce sola en el mapa con la línea de tiempo; «Otra década posible» cambia a la siguiente)
sobre la banda p10–p90 de las 500, cuántos de los 11 años quedan en caudal crítico en promedio y en qué parte
de las décadas hay tres años críticos seguidos. La semilla es fija: los números se repiten. No es un modelo
climático: supone que la próxima década se parece al período elegido, y la hoja lo dice.

**Unidad del índice** (`src/lib/riesgo.ts`): en cada variable, el riesgo de una comuna es el porcentaje de las
otras comunas que están mejor que ella en ese año (0 = la mejor, 100 = la peor). El índice general es el promedio
de esos riesgos, ponderado por la prioridad de 0 a 10 que se le da a cada variable (los perfiles de
`tipos_hogar` son prioridades ya puestas). Entran siete variables: las tres simuladas y los cuatro indicadores
de inversión (ver «Las siete variables del índice»); una variable con peso 0 no cuenta. Hasta 33 es riesgo bajo; hasta 66, medio; más, alto. Se usa la
posición y no el valor porque las unidades son distintas y hay comunas muy alejadas del resto.
Es un índice relativo a la región: no dice si el valor es bueno en términos absolutos; para el aire, eso lo dice
la norma, y por eso la fila de aire marca «Sobre la norma» aunque la posición sea buena.

### Entrada guiada

Al abrir, una sola pantalla sobre el mapa (`src/components/Onboarding.tsx`): **el caso, en texto libre**.
Claude lo lee y elige uno de nueve perfiles (`PERFILES` en `src/lib/caso.ts`): familia con niños, adulto mayor,
joven que arrienda, inversionista inmobiliario, emprendedor o comercio, empresario joven u oficina, industria y
logística, energía o evaluación general. Cada perfil da un peso a las siete variables del índice y parte con
tres activas (por ejemplo, industria apaga el aire y usa la red eléctrica); Claude puede subir o bajar cualquiera.
Tres es la base, no un tope: con «Ajustar pesos» o escribiendo un cambio («el agua es clave») se suman más
indicadores y el orden se recalcula al instante;
`leerCaso` (`src/lib/onboarding.ts`) clasifica por palabras clave solo cuando Claude no responde. No hay más
preguntas. `npm run evaluar` prueba frases de ejemplo contra el modelo real (`scripts/evaluar-casos.eval.ts`,
reporte en `docs/evaluacion-casos.md`).
Los criterios propios del caso que el modelo no mide (caída disponible, precio del suelo, etc.) **no entran al
cálculo ni muestran número**: la guía los nombra como «aún sin datos», porque para usarlos hace falta un valor
por comuna que hoy no existe. El caudal sí tiene datos y se ve en Climático › El agua.

Ya en el mapa, «Ajustar pesos» abre el peso de las siete variables (0 a 10; subir una en 0 la enciende) y el rango que se acepta: para el aire,
la norma chilena o las metas de la OMS; para seguridad y crecimiento, cortes sobre los datos de la región. Las
tres de menor riesgo salen solo de las comunas que cumplen todos los rangos, y la ficha marca «Fuera de tu
rango» donde corresponde. Con `?directo` en la dirección la entrada no aparece.

La explicación la arma la propia interfaz con los números del índice (`src/lib/onboarding.ts`). Si al construir
se define `VITE_GUIA_URL` con la dirección de un intermediario propio y la persona escribió su caso, se le pide
a ese intermediario un texto redactado por un modelo de lenguaje (`src/lib/guia.ts`):

- Pedido: `POST` con JSON `{ perfil, contexto, prioridades, anio, top, falta }`; `top` trae las tres comunas de
  menor riesgo con los valores de las variables que pesan, indicadores incluidos. Respuesta: JSON `{ "texto": "..." }`.
- La clave del modelo vive en el intermediario, nunca en esta página. El intermediario debe permitir el origen
  de la página (CORS) y limitar el uso.
- El modelo solo redacta: el orden de las comunas lo calcula siempre el índice. Si el intermediario no está,
  tarda más de 12 s o responde otra cosa, queda la explicación propia.
- Lo que escribe la persona sale de la página solo en ese pedido; sin `VITE_GUIA_URL` no sale nunca.
- Con `VITE_CASO_URL` (ruta `/interpretar` de `servidor-guia/`), antes de ordenar se le pide a Claude que lea el
  caso y proponga ajustes de prioridad de un catálogo cerrado (`src/lib/caso.ts`). La persona los ve como
  «Por lo que contaste: Aire: Clave» y puede apagarlos; el índice recalcula el orden. Detalle en
  `servidor-guia/README.md`.
  Esa misma llamada se hace desde la entrada y **no hace preguntas de seguimiento**: Claude infiere todo del caso
  y del perfil (en comercio, industria y energía el aire no pesa). El mapa reusa esa lectura en vez de
  pedir otra.

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
| `1` … `5` | Pestañas: Resumen, Climático, Legal, Social y Referencias |
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

### Horizonte de 10 o 15 años

Abajo a la derecha se elige «10 años» (2026–2036, el período que cubren los supuestos documentados del modelo)
o «15 años» (hasta 2040). El segundo carga `viz/datos/simulacion-15.json` y `viz/public/datos/demografia-15.json`,
que salen de la misma simulación con `python -m experiments.simular --hasta 2040 --salida viz/datos/simulacion-15.json`
y `python -m experiments.exportar_demografia --hasta 2040 --salida viz/public/datos/demografia-15.json`. Los años
2037–2040 vienen marcados en `meta.anios_extrapolados`: sus pestañas van rayadas y el pie dice «extrapolación,
fuera del período validado», porque ahí el modelo sigue con las mismas tasas y nada lo valida. Cambiar de
horizonte no borra el caso, los pesos ni la comuna elegida. También se puede abrir con `?horizonte=15`.

### Las siete variables del índice

Además de las tres simuladas, el índice suma cuatro indicadores de inversión (`src/lib/inversion.ts`:
`comoVariables`, `sumarIndicadores`). Entran como cualquier variable, con el peso que les dé el perfil o la
persona; la ficha del resumen muestra solo las que pesan. No tienen serie ni capa de detalle: su fila da la
posición y el valor del año, sin tendencia ni enlace. Se probaron antes en una simulación
(`npm run evaluar -- simular-indicadores`, reporte en `docs/simulacion-indicadores.md`).

| Variable | De dónde sale |
|---|---|
| Sequía futura | Simulada: cambio de la frecuencia de sequía del año elegido, bloque `clima` de la simulación (ARClim) |
| Escasez hídrica | Dato real: años con decreto de escasez de la DGA, 2008–2023 |
| Red eléctrica | Dato real: MVA de subestaciones en operación (Coordinador Eléctrico) |
| Inversión evaluada | Dato real: proyectos aprobados en el SEIA desde 2015 |

Las tres reales vienen de `viz/public/datos/inversion.json` (`python -I datos/viz/build_inversion.py`). Un
indicador que cubre menos de la mitad de las comunas o vale lo mismo en todas no entra (por eso no se usa
la amenaza de sequía de ARClim de ese archivo: solo 9 comunas, todas en 1,0).

### Pantalla de espera

Entre la entrada y el mapa (`src/components/Cargando.tsx`) se listan cinco pasos y la región se dibuja al ritmo
de ellos: contornos, ríos, comunas con plan y color de riesgo. Dos pasos esperan algo real (la lectura del caso
y que el mapa tenga algo que mostrar); el tope es de 14 s.

### Dónde van los datos

| Archivo | Quién lo pone | Qué pasa si falta |
|---|---|---|
| `viz/datos/simulacion.json` (lo sirve y empaqueta `vite.config.ts` como `datos/simulacion.json`) | El modelo: `python -m experiments.simular` | Se usa `viz/ejemplo/simulacion.json` (se sirve como `datos/ejemplo.json` por un plugin de `vite.config.ts`) y aparece «Datos de ejemplo» si `meta.es_ejemplo` es true |
| `viz/public/datos/lena.json` | `datos/viz/build_lena.py` | La vista La leña lo dice en palabras |
| `viz/public/datos/demografia.json` | `python -m experiments.exportar_demografia` | La vista Las mudanzas no aparece. Es la simulación por agentes de `docs/modelo-mudanzas-abm.md`: corre en un Web Worker (`src/lib/abm.worker.ts`), 20 corridas por cambio, y el mapa pinta la ocupación de la vivienda |
| `viz/public/datos/caudales.json` y `viz/public/geo/rios_rm.geojson` | `python -m datos.dga.fetch_caudales` y después `python -m datos.dga.rios_teselas` (DGA compilado por CR2, CC0; cauces de OpenStreetMap, ODbL, leídos de las teselas de OpenFreeMap) | La sección El agua no aparece; sin el segundo archivo se ven las estaciones sin ríos |
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

### Aporte de cada proyecto y de cada licitación

En Referencias › «Cuánto aportó cada licitación y cada proyecto», la primera sección de la pestaña
(`src/components/VistaAportes.tsx`, `src/lib/aportes.ts`), la comuna elegida muestra sus licitaciones de 2024 y sus
proyectos SEIA (cada uno suma 1 a «inversión evaluada»). Cada licitación muestra primero su aporte propio a la
credibilidad municipal, en puntos con signo; la fila se abre para ver su estado, sector, montos, oferentes y cuánto
sería la credibilidad sin ella. Por defecto se ordenan por aporte. Los avisos quedan junto a la lista: todas las
adjudicadas aportan lo mismo y todas las fallidas también, los aportes no suman el total por el tope de licitaciones
efectivas, y no se muestra el efecto sobre los delitos. Las licitaciones se piden por comuna desde
`public/datos/licitaciones/<codigo>.json`, que genera `python -I datos/viz/partir_licitaciones.py` a partir de
`viz/datos/licitaciones.json`. Solo cinco comunas usan las licitaciones en el modelo; en las demás la vista dice
que son contexto. Si un archivo no carga, la sección lo indica y el resto sigue igual.

### Cambiar el requerimiento desde el resumen

Bajo el texto del resumen hay una línea para reescribir lo que se necesita («ahora me importa más la seguridad
que el aire»). Sin el intermediario, `ajustarPorTexto` (`src/lib/onboarding.ts`) sube o baja las variables que
cada frase nombra; con él, el cambio se suma al caso y Claude lo lee completo.
