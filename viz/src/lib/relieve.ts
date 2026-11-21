/**
 * Lógica pura del mapa en relieve (MapLibre): qué mapa usar, cómo se arma el estilo y utilidades de color y curvas.
 * Sin dependencias del navegador ni de MapLibre, para poder probarla en Node.
 */

export type TipoMapa = 'linea' | 'local' | 'plano'

/** Estilo del mapa base en línea (OpenFreeMap, sin clave) y relieve (Mapterhorn, sin clave). */
export const ESTILO_LINEA = 'https://tiles.openfreemap.org/styles/positron'
export const RELIEVE_LINEA = 'https://tiles.mapterhorn.com/tilejson.json'
/** Paquete predescargado con `npm run mapas` (queda en public/mapas, fuera de git). */
export const ESTILO_LOCAL = 'mapas/estilo.json'
/** Marca que el script de descarga deja en las rutas del paquete local; se cambia por la URL absoluta al cargar. */
export const MARCA_BASE = '__BASE__'

export interface Sondas {
  /** Devuelve el estilo base si se pudo leer, o null. */
  linea: () => Promise<unknown | null>
  local: () => Promise<unknown | null>
}

export interface MapaElegido {
  tipo: TipoMapa
  estilo: unknown | null
}

/**
 * Orden de respaldo: en línea, luego el paquete local, luego el mapa plano.
 * `pedido` (parámetro ?mapa=) fuerza el punto de partida: "local" salta la red y "plano" no carga nada.
 */
export async function elegirMapa(pedido: string | null, sondas: Sondas): Promise<MapaElegido> {
  if (pedido === 'plano') return { tipo: 'plano', estilo: null }
  if (pedido !== 'local') {
    const e = await sondas.linea()
    if (e) return { tipo: 'linea', estilo: e }
  }
  const l = await sondas.local()
  if (l) return { tipo: 'local', estilo: l }
  return { tipo: 'plano', estilo: null }
}

/** Siguiente mapa al pedir el cambio manual de emergencia. */
export function siguienteMapa(t: TipoMapa): TipoMapa {
  return t === 'linea' ? 'local' : t === 'local' ? 'plano' : 'linea'
}

const esObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)

/** Un estilo base sirve si tiene la fuente vectorial y capas. */
export function esEstiloValido(v: unknown): boolean {
  return esObj(v) && esObj(v.sources) && esObj(v.sources.openmaptiles) && Array.isArray(v.layers) && v.layers.length > 0
}

/** Cambia la marca del paquete local por la URL absoluta de la carpeta `mapas/`. */
export function resolverBase(estilo: unknown, base: string): unknown {
  return JSON.parse(JSON.stringify(estilo).split(MARCA_BASE).join(base.replace(/\/$/, '')))
}

export interface ColoresRelieve {
  tinta: string
  papel: string
  disco: string
  corte: string
  edificio: string
  /** el agua de los ríos y el brillo que corre sobre ella */
  agua: string
  aguaClara: string
}

export const CAPAS = {
  relleno: 'c-relleno',
  trama: 'c-trama',
  linea: 'c-linea',
  nombres: 'c-nombres',
  riosFilo: 'rios-filo',
  riosBase: 'rios-base',
  rios: 'rios',
  flujoBase: 'rios-flujo-base',
  flujo: 'rios-flujo',
  estaciones: 'estaciones',
  pulso: 'estaciones-pulso',
} as const

const VACIO = { type: 'FeatureCollection', features: [] }
/** píxeles por metro a zoom 0 en la latitud de Santiago (teselas de 512 px) */
const PX_POR_METRO_Z0 = 1 / (78271.517 * Math.cos((33.45 * Math.PI) / 180))

const estado = (k: string) => ['boolean', ['feature-state', k], false]
const ES_RIO = ['==', ['get', 'class'], 'river']
const NINGUNO = ['==', ['get', 'class'], '__ninguno__']

/** Capa de línea sobre los cauces de las teselas del mapa base; oculta hasta que se muestra el agua. */
function capaRio(id: string, filter: unknown, paint: Record<string, unknown>, redonda: boolean): Record<string, unknown> {
  return {
    id,
    type: 'line',
    source: 'openmaptiles',
    'source-layer': 'waterway',
    filter,
    layout: { visibility: 'none', 'line-join': 'round', ...(redonda ? { 'line-cap': 'round' } : {}) },
    paint,
  }
}

/** Capas de ríos, de abajo hacia arriba. */
export const CAPAS_RIOS = ['rios-filo', 'rios-base', 'rios', 'rios-flujo-base', 'rios-flujo'] as const

export interface CauceAncho {
  /** nombres con que el cauce puede venir en las teselas */
  nombres: readonly string[]
  ancho: number
}

/** Filtro de los cauces medidos: su nombre es uno de los conocidos y están dentro de la región (hay ríos homónimos fuera). */
export function filtroCauces(cauces: readonly CauceAncho[], limites: readonly [number, number, number, number]): unknown {
  const [o, s, e, n] = limites
  const nombres = cauces.flatMap((c) => c.nombres)
  if (nombres.length === 0) return NINGUNO
  return [
    'all',
    ['in', ['get', 'name'], ['literal', nombres]],
    ['within', { type: 'Polygon', coordinates: [[[o, s], [e, s], [e, n], [o, n], [o, s]]] }],
  ]
}

/** Un valor por nombre de cauce (color, opacidad…), con uno por defecto para los demás. */
export function porCauce<T>(cauces: readonly { nombres: readonly string[]; valor: T }[], defecto: T): unknown {
  const con = cauces.filter((c) => c.nombres.length > 0)
  if (con.length === 0) return defecto
  return ['match', ['get', 'name'], ...con.flatMap((c) => [[...c.nombres], c.valor]), defecto]
}

/** Ancho de línea por nombre de cauce, multiplicado por `k` y con `mas` píxeles de filo. */
export function anchoCauces(cauces: readonly CauceAncho[], k = 1, mas = 0, piso = 0): unknown {
  const con = cauces.filter((c) => c.nombres.length > 0)
  if (con.length === 0) return Math.max(piso, 1.3 * k + mas)
  const pares = con.flatMap((c) => [[...c.nombres], Math.max(piso, c.ancho * k + mas)])
  return ['match', ['get', 'name'], ...pares, Math.max(piso, 1.3 * k + mas)]
}

/**
 * Secuencia de trazos que, puesta una tras otra, hace correr el brillo del río en el sentido de la línea
 * (la técnica de la «hilera de hormigas» de MapLibre). Cada paso corre el trazo medio guion.
 */
export const TRAZOS_FLUJO: readonly number[][] = [
  [0, 4, 3],
  [0.5, 4, 2.5],
  [1, 4, 2],
  [1.5, 4, 1.5],
  [2, 4, 1],
  [2.5, 4, 0.5],
  [3, 4, 0],
  [0, 0.5, 3, 3.5],
  [0, 1, 3, 3],
  [0, 1.5, 3, 2.5],
  [0, 2, 3, 2],
  [0, 2.5, 3, 1.5],
  [0, 3, 3, 1],
  [0, 3.5, 3, 0.5],
]

/**
 * Estilo completo del mapa en relieve a partir del estilo base: quita los rótulos de lugares (las comunas
 * llevan los suyos), agrega el terreno, las sombras, el cielo y las capas de datos, vacías hasta que la
 * pantalla les pase las comunas.
 */
export function estiloRelieve(baseRaw: unknown, c: ColoresRelieve, exageracion = 1.5): Record<string, unknown> {
  if (!esObj(baseRaw) || !esObj(baseRaw.sources) || !Array.isArray(baseRaw.layers)) throw new Error('Estilo base inválido')
  const base = baseRaw
  const fuentes: Record<string, unknown> = { ...(base.sources as Record<string, unknown>) }
  delete fuentes.ne2_shaded
  if (!fuentes['relieve-dem']) fuentes['relieve-dem'] = { type: 'raster-dem', url: RELIEVE_LINEA }
  // Una fuente aparte para las sombras: compartirla con el terreno baja la calidad del sombreado.
  fuentes['relieve-sombra'] = { ...(fuentes['relieve-dem'] as object) }
  for (const id of ['comunas', 'rotulos', 'cintas', 'discos', 'estaciones']) fuentes[id] = { type: 'geojson', data: VACIO }

  const capas = (base.layers as Record<string, unknown>[]).filter(
    (l) => l.source !== 'ne2_shaded' && !(l.type === 'symbol' && l['source-layer'] === 'place'),
  )
  const datos: Record<string, unknown>[] = [
    { id: 'sombras', type: 'hillshade', source: 'relieve-sombra', paint: { 'hillshade-shadow-color': '#4f4539', 'hillshade-exaggeration': 0.5 } },
    {
      id: CAPAS.relleno,
      type: 'fill',
      source: 'comunas',
      paint: {
        'fill-color': ['to-color', ['coalesce', ['feature-state', 'color'], c.papel]],
        'fill-opacity': ['case', ['all', estado('dato'), estado('hover')], 0.86, estado('dato'), 0.54, 0],
        'fill-antialias': false,
      },
    },
    { id: CAPAS.linea, type: 'line', source: 'comunas', paint: { 'line-color': c.papel, 'line-width': 1.3, 'line-opacity': 0.95 } },
    {
      id: 'edificios-3d',
      type: 'fill-extrusion',
      source: 'openmaptiles',
      'source-layer': 'building',
      minzoom: 13,
      paint: {
        'fill-extrusion-color': c.edificio,
        'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 6],
        'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
        'fill-extrusion-opacity': 0.9,
      },
    },
    {
      id: 'cintas-filo',
      type: 'line',
      source: 'cintas',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': c.papel, 'line-width': ['+', ['get', 'ancho'], 3] },
    },
    {
      id: 'cintas',
      type: 'line',
      source: 'cintas',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': c.tinta, 'line-width': ['get', 'ancho'] },
    },
    {
      id: 'discos',
      type: 'circle',
      source: 'discos',
      paint: {
        'circle-pitch-alignment': 'map',
        'circle-pitch-scale': 'map',
        'circle-radius': [
          'interpolate',
          ['exponential', 2],
          ['zoom'],
          0,
          ['*', ['get', 'r'], PX_POR_METRO_Z0],
          22,
          ['*', ['get', 'r'], PX_POR_METRO_Z0 * 2 ** 22],
        ],
        'circle-color': ['case', ['get', 'dato'], c.disco, c.corte],
        'circle-stroke-color': c.papel,
        'circle-stroke-width': 1.5,
      },
    },
    // Ríos: salen de la capa de cauces de las mismas teselas del mapa base, así que no hay otro archivo que
    // cargar. Los medidos llevan un filo de papel y un ancho según su caudal; todos, un brillo de trazos que
    // corre aguas abajo. Parten ocultos: la pantalla los enciende, les da el filtro y el ancho.
    capaRio('rios-filo', NINGUNO, { 'line-color': c.papel, 'line-opacity': 0.85, 'line-width': 3 }, true),
    capaRio(CAPAS.riosBase, ES_RIO, { 'line-color': c.agua, 'line-width': 1.3 }, true),
    capaRio(CAPAS.rios, NINGUNO, { 'line-color': c.agua, 'line-width': 2 }, true),
    capaRio(CAPAS.flujoBase, ES_RIO, { 'line-color': c.aguaClara, 'line-opacity': 0.9, 'line-width': 0.7, 'line-dasharray': TRAZOS_FLUJO[0] }, false),
    capaRio(CAPAS.flujo, NINGUNO, { 'line-color': c.aguaClara, 'line-opacity': 0.9, 'line-width': 1, 'line-dasharray': TRAZOS_FLUJO[0] }, false),
    {
      id: CAPAS.pulso,
      type: 'circle',
      source: 'estaciones',
      // solo laten las estaciones con caudal crítico en lo que se mira
      filter: ['==', ['get', 'late'], true],
      paint: { 'circle-radius': ['get', 'r'], 'circle-color': ['get', 'color'], 'circle-opacity': 0, 'circle-pitch-alignment': 'map' },
    },
    {
      id: CAPAS.estaciones,
      type: 'circle',
      source: 'estaciones',
      paint: {
        'circle-radius': ['case', ['get', 'sel'], ['+', ['get', 'r'], 2], ['get', 'r']],
        'circle-color': ['get', 'color'],
        'circle-stroke-color': ['case', ['get', 'sel'], c.tinta, c.papel],
        'circle-stroke-width': ['case', ['get', 'sel'], 3.5, 1.8],
        'circle-pitch-alignment': 'map',
      },
    },
    { id: 'c-hover', type: 'line', source: 'comunas', paint: { 'line-color': c.tinta, 'line-width': ['case', estado('hover'), 2.6, 0] } },
    {
      id: 'c-elegida-filo',
      type: 'line',
      source: 'comunas',
      layout: { 'line-join': 'round' },
      paint: { 'line-color': c.papel, 'line-width': ['case', estado('sel'), 8, 0] },
    },
    {
      id: 'c-elegida',
      type: 'line',
      source: 'comunas',
      layout: { 'line-join': 'round' },
      paint: { 'line-color': c.tinta, 'line-width': ['case', estado('sel'), 4.5, 0] },
    },
  ]
  const i = capas.findIndex((l) => l.type === 'symbol')
  capas.splice(i < 0 ? capas.length : i, 0, ...datos)
  capas.push({
    id: CAPAS.nombres,
    type: 'symbol',
    source: 'rotulos',
    layout: {
      'text-field': ['get', 'nombre'],
      'text-font': ['Noto Sans Bold'],
      'text-size': ['interpolate', ['linear'], ['zoom'], 8, 11, 11, 14, 14, 17],
      'text-padding': 5,
      'text-max-width': 7,
      'symbol-sort-key': ['get', 'orden'],
    },
    paint: { 'text-color': c.tinta, 'text-halo-color': c.papel, 'text-halo-width': 1.8 },
  })

  return {
    ...base,
    sources: fuentes,
    layers: capas,
    terrain: { source: 'relieve-dem', exaggeration: exageracion },
    sky: {
      'sky-color': '#cfe0ea',
      'horizon-color': '#f3f1e8',
      'fog-color': '#f3f1e8',
      'sky-horizon-blend': 0.6,
      'horizon-fog-blend': 0.6,
      'fog-ground-blend': 0.25,
    },
  }
}

export type RGB = [number, number, number]

/** "#rgb", "#rrggbb" o "rgb(r, g, b)" a componentes; null si no se entiende. */
export function aRgb(s: string): RGB | null {
  const t = s.trim()
  let m = /^#([0-9a-f]{3})$/i.exec(t)
  if (m) return [...m[1]!].map((x) => parseInt(x + x, 16)) as RGB
  m = /^#([0-9a-f]{6})$/i.exec(t)
  if (m) return [0, 2, 4].map((i) => parseInt(m![1]!.slice(i, i + 2), 16)) as RGB
  m = /^rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/i.exec(t)
  if (m) return [Number(m[1]), Number(m[2]), Number(m[3])]
  return null
}

export function mezclar(a: RGB, b: RGB, t: number): RGB {
  const k = Math.min(1, Math.max(0, t))
  return [0, 1, 2].map((i) => Math.round(a[i]! + (b[i]! - a[i]!) * k)) as RGB
}

export const textoRgb = (c: RGB) => `rgb(${c[0]},${c[1]},${c[2]})`

/** Curva suave entre dos puntos (lon, lat), combada hacia un lado, como las cintas del mapa plano. */
export function curva(a: readonly [number, number], b: readonly [number, number], comba = 0.22, pasos = 24): [number, number][] {
  const mx = (a[0] + b[0]) / 2 - (b[1] - a[1]) * comba
  const my = (a[1] + b[1]) / 2 + (b[0] - a[0]) * comba
  const out: [number, number][] = []
  for (let i = 0; i <= pasos; i++) {
    const t = i / pasos
    const u = 1 - t
    out.push([u * u * a[0] + 2 * u * t * mx + t * t * b[0], u * u * a[1] + 2 * u * t * my + t * t * b[1]])
  }
  return out
}
