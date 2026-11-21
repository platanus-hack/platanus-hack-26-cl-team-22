/**
 * Caudales reales de los ríos (viz/public/datos/caudales.json y geo/rios_rm.geojson, generados por
 * datos/dga/fetch_caudales.py). Son archivos externos: se validan campo por campo y lo que no calza se descarta.
 */

export interface Estacion {
  codigo: string
  nombre: string
  rio: string
  lon: number
  lat: number
  altitud: number | null
  /** código de la comuna donde está, como en comunas_rm.geojson; null si no se pudo asignar */
  comuna: string | null
  subcuenca: string
  /** caudal medio de cada año de `anios`, en m³/s; null = año sin datos suficientes */
  anual: (number | null)[]
  /** caudal medio de cada mes, de enero a diciembre */
  regimen: number[]
  medio: number
  base: number | null
  sequia: number | null
  /** cambio porcentual de la megasequía frente al período base; null si falta alguno */
  cambio: number | null
  /** desviación estándar sobre media de los caudales mensuales */
  cv: number | null
  /** página con el caudal en tiempo real de esta estación; null si no hay */
  vivo: string | null
}

export interface Rio {
  nombre: string | null
  clase: 'river' | 'stream'
  /** estación que representa a este cauce; null si ninguna lo mide */
  estacion: string | null
  /** vértices (lon, lat) en el sentido en que corre el agua */
  coords: [number, number][]
}

/** Un río con nombre: por qué comunas pasa y qué estación lo mide. */
export interface CauceDato {
  nombre: string
  clase: 'river' | 'stream'
  estacion: string | null
  /** códigos de comuna, de aguas arriba a aguas abajo */
  comunas: string[]
  /** kilómetros dentro de la región */
  largoKm: number | null
}

export interface Agua {
  fuente: string
  url: string | null
  licencia: string
  descarga: string
  anios: number[]
  base: [number, number]
  sequia: [number, number]
  estaciones: Estacion[]
  rios: Rio[]
  cauces: CauceDato[]
  porCodigo: ReadonlyMap<string, Estacion>
}

type Obj = Record<string, unknown>
const esObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)
const esNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const texto = (v: unknown, max = 90): string => (typeof v === 'string' ? v.replace(/\s+/g, ' ').trim().slice(0, max) : '')
const caudal = (v: unknown): number | null => (esNum(v) && v >= 0 && v < 1e5 ? v : null)

/** La región con holgura: una coordenada fuera de aquí es un error del archivo. */
const enRegion = (lon: unknown, lat: unknown): boolean => esNum(lon) && esNum(lat) && lon > -72.5 && lon < -69 && lat > -35 && lat < -32.3

const VIVO = /^https:\/\/caudalrio\.cl\/caudal\/[a-z0-9-]{3,120}$/
const par = (v: unknown, def: [number, number]): [number, number] =>
  Array.isArray(v) && v.length === 2 && Number.isInteger(v[0]) && Number.isInteger(v[1]) && v[0] <= v[1] ? [v[0] as number, v[1] as number] : def

function leerEstacion(raw: unknown, nAnios: number): Estacion | null {
  if (!esObj(raw)) return null
  const codigo = texto(raw.codigo, 12)
  const nombre = texto(raw.nombre)
  const medio = caudal(raw.medio)
  if (!/^\d{5,9}$/.test(codigo) || !nombre || medio === null || !enRegion(raw.lon, raw.lat)) return null
  if (!Array.isArray(raw.anual) || raw.anual.length !== nAnios) return null
  if (!Array.isArray(raw.regimen) || raw.regimen.length !== 12) return null
  const regimen = raw.regimen.map(caudal)
  if (regimen.some((x) => x === null)) return null
  const comuna = texto(raw.comuna, 8)
  const vivo = typeof raw.vivo === 'string' && VIVO.test(raw.vivo) ? raw.vivo : null
  return {
    codigo,
    nombre,
    rio: texto(raw.rio) || nombre,
    lon: raw.lon as number,
    lat: raw.lat as number,
    altitud: esNum(raw.altitud) && raw.altitud > 0 && raw.altitud < 7000 ? raw.altitud : null,
    comuna: /^\d{4,5}$/.test(comuna) ? comuna : null,
    subcuenca: texto(raw.subcuenca),
    anual: raw.anual.map(caudal),
    regimen: regimen as number[],
    medio,
    base: caudal(raw.base),
    sequia: caudal(raw.sequia),
    cambio: esNum(raw.cambio) && raw.cambio > -100.5 && raw.cambio < 1000 ? raw.cambio : null,
    cv: esNum(raw.cv) && raw.cv >= 0 && raw.cv < 50 ? raw.cv : null,
    vivo,
  }
}

const MAX_RIOS = 3000
const MAX_VERTICES = 4000

function leerRios(raw: unknown, codigos: ReadonlySet<string>): Rio[] {
  if (!esObj(raw) || !Array.isArray(raw.features)) return []
  const out: Rio[] = []
  for (const f of raw.features.slice(0, MAX_RIOS)) {
    if (!esObj(f) || !esObj(f.geometry) || f.geometry.type !== 'LineString' || !Array.isArray(f.geometry.coordinates)) continue
    const coords: [number, number][] = []
    for (const c of f.geometry.coordinates.slice(0, MAX_VERTICES)) {
      if (Array.isArray(c) && enRegion(c[0], c[1])) coords.push([c[0] as number, c[1] as number])
    }
    if (coords.length < 2) continue
    const p = esObj(f.properties) ? f.properties : {}
    const estacion = texto(p.estacion, 12)
    out.push({
      nombre: texto(p.nombre) || null,
      clase: p.clase === 'stream' ? 'stream' : 'river',
      estacion: codigos.has(estacion) ? estacion : null,
      coords,
    })
  }
  return out
}

function leerCauces(raw: unknown, codigos: ReadonlySet<string>): CauceDato[] {
  if (!Array.isArray(raw)) return []
  const out: CauceDato[] = []
  for (const c of raw.slice(0, 300)) {
    if (!esObj(c)) continue
    const nombre = texto(c.nombre)
    if (!nombre) continue
    const estacion = texto(c.estacion, 12)
    const comunas = Array.isArray(c.comunas) ? c.comunas.map((x) => texto(x, 8)).filter((x) => /^\d{4,5}$/.test(x)).slice(0, 60) : []
    out.push({
      nombre,
      clase: c.clase === 'stream' ? 'stream' : 'river',
      estacion: codigos.has(estacion) ? estacion : null,
      comunas: [...new Set(comunas)],
      largoKm: esNum(c.largo_km) && c.largo_km > 0 && c.largo_km < 2000 ? c.largo_km : null,
    })
  }
  return out
}

/** Lee los dos archivos. Devuelve null si no hay ninguna estación válida; los ríos pueden faltar. */
export function leerAgua(raw: unknown, riosRaw: unknown): Agua | null {
  if (!esObj(raw) || !esObj(raw.meta) || !Array.isArray(raw.estaciones)) return null
  const periodo = par(raw.meta.periodo, [0, -1])
  const n = periodo[1] - periodo[0] + 1
  if (n < 5 || n > 150) return null
  const anios = Array.from({ length: n }, (_, i) => periodo[0] + i)
  const vistos = new Set<string>()
  const estaciones: Estacion[] = []
  for (const r of raw.estaciones.slice(0, 400)) {
    const e = leerEstacion(r, n)
    if (!e || vistos.has(e.codigo)) continue
    vistos.add(e.codigo)
    estaciones.push(e)
  }
  if (estaciones.length === 0) return null
  estaciones.sort((a, b) => b.medio - a.medio)
  const url = typeof raw.meta.url === 'string' && /^https:\/\/[a-z0-9.-]+\//i.test(raw.meta.url) ? raw.meta.url.slice(0, 200) : null
  return {
    fuente: texto(raw.meta.fuente, 160) || 'Dirección General de Aguas',
    url,
    licencia: texto(raw.meta.licencia, 40),
    descarga: texto(raw.meta.descarga, 12),
    anios,
    base: par(raw.meta.base, [periodo[0], periodo[0]]),
    sequia: par(raw.meta.sequia, [periodo[1], periodo[1]]),
    estaciones,
    rios: leerRios(riosRaw, vistos),
    cauces: leerCauces(raw.cauces, vistos),
    porCodigo: new Map(estaciones.map((e) => [e.codigo, e])),
  }
}

export type TonoCambio = 'sin' | 'estable' | 'baja' | 'fuerte' | 'critica'

/** Qué tan fuerte fue la caída del caudal en la megasequía. */
export function tonoCambio(cambio: number | null): TonoCambio {
  if (cambio === null) return 'sin'
  if (cambio > -10) return 'estable'
  if (cambio > -25) return 'baja'
  if (cambio > -45) return 'fuerte'
  return 'critica'
}

export const TEXTO_TONO: Record<TonoCambio, string> = {
  sin: 'Sin comparación',
  estable: 'Se mantiene',
  baja: 'Baja',
  fuerte: 'Baja fuerte',
  critica: 'Baja crítica',
}

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'] as const
export const MESES_CORTOS = ['E', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'] as const

export interface Regimen {
  /** mes de mayor caudal, de 0 (enero) a 11 */
  mesAlto: number
  mesBajo: number
  /** de deshielo si el máximo cae entre octubre y febrero; de lluvia si cae en otoño o invierno */
  tipo: 'deshielo' | 'lluvia'
  texto: string
}

export function regimenDe(regimen: readonly number[]): Regimen {
  let alto = 0
  let bajo = 0
  regimen.forEach((v, i) => {
    if (v > regimen[alto]!) alto = i
    if (v < regimen[bajo]!) bajo = i
  })
  const tipo = alto >= 9 || alto <= 1 ? 'deshielo' : 'lluvia'
  return {
    mesAlto: alto,
    mesBajo: bajo,
    tipo,
    texto: tipo === 'deshielo' ? `De deshielo: máximo en ${MESES[alto]}` : `De lluvia: máximo en ${MESES[alto]}`,
  }
}

/** Lectura del coeficiente de variación de los caudales mensuales. */
export function variabilidad(cv: number | null): string {
  if (cv === null) return 'Sin dato'
  if (cv < 0.5) return 'Caudal parejo'
  if (cv < 1) return 'Caudal variable'
  return 'Caudal muy variable'
}

/** Caudal del año `i` sobre el caudal medio; 1 si se pide el promedio (i null) o el año no tiene dato. */
export function factorAnio(e: Estacion, i: number | null): number {
  if (i === null || e.medio <= 0) return 1
  const v = e.anual[i]
  return v === null || v === undefined ? 1 : v / e.medio
}

/** Ancho en píxeles de un cauce: crece con la raíz del caudal, para que un estero no desaparezca junto al Maipo. */
export function anchoRio(caudalM3s: number | null, clase: Rio['clase']): number {
  if (caudalM3s === null) return clase === 'river' ? 1.3 : 0.8
  return Math.min(12, Math.max(1.4, 1.6 + Math.sqrt(Math.max(0, caudalM3s)) * 0.85))
}

/** Radio en píxeles del punto de una estación. */
export function radioEstacion(medio: number): number {
  return Math.min(13, 4.5 + Math.sqrt(Math.max(0, medio)) * 0.7)
}

/** La estación de más caudal dentro de una comuna; null si la comuna no tiene ninguna. */
export function estacionDeComuna(estaciones: readonly Estacion[], comuna: string | null | undefined): Estacion | null {
  if (!comuna) return null
  let mejor: Estacion | null = null
  for (const e of estaciones) if (e.comuna === comuna && (!mejor || e.medio > mejor.medio)) mejor = e
  return mejor
}

const sinAcentos = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '')

/** Otras formas en que el mapa base escribe un cauce (el nombre de la estación viene sin acentos ni artículos). */
const OTROS_NOMBRES: Record<string, readonly string[]> = {
  'estero alhue': ['Estero Alhué', 'Estero de Alhué'],
  'estero arrayan': ['Estero Arrayán', 'Estero El Arrayán', 'Estero del Arrayán'],
  'quebrada ramon': ['Quebrada de Ramón', 'Quebrada Ramón', 'Quebrada San Ramón', 'Quebrada de San Ramón'],
  'rio volcan': ['Río Volcán', 'Río El Volcán'],
  'estero yerba loca': ['Estero Yerba Loca', 'Estero de la Yerba Loca'],
}

export interface Cauce {
  /** nombres con que puede venir en el mapa base */
  nombres: string[]
  /** la estación de más caudal sobre ese cauce: la que lo representa */
  estacion: Estacion
}

const ARTICULOS = new Set(['de', 'del', 'la', 'el', 'los', 'las', 'san'])
/** Cauces que la DGA y el mapa nombran con distinto tipo. */
const OTRA_CLAVE: Record<string, string> = { 'estero puangue': 'rio puangue' }

/** «Quebrada de Ramón» y «Quebrada Ramon» son el mismo cauce (misma regla que datos/dga/rios_teselas.py). */
export function claveCauce(nombre: string): string {
  const k = (sinAcentos(nombre).toLowerCase().match(/[a-z0-9]+/g) ?? []).filter((w) => !ARTICULOS.has(w)).join(' ')
  return OTRA_CLAVE[k] ?? k
}

/** El río con nombre que mide una estación: por dónde pasa. null si el archivo no lo trae. */
export function cauceDe(agua: Pick<Agua, 'cauces'>, e: Estacion): CauceDato | null {
  const k = claveCauce(e.rio)
  return agua.cauces.find((c) => claveCauce(c.nombre) === k) ?? null
}

/**
 * Un cauce por río medido, con la estación que lo representa y las formas de su nombre en el mapa base.
 * Si el archivo trae el río mapeado se usa ese nombre; si no, se prueban las variantes conocidas.
 */
export function caucesMedidos(estaciones: readonly Estacion[], mapeados: readonly CauceDato[] = []): Cauce[] {
  const porRio = new Map<string, Estacion>()
  for (const e of estaciones) {
    const k = claveCauce(e.rio)
    const previa = porRio.get(k)
    if (!previa || e.medio > previa.medio) porRio.set(k, e)
  }
  return [...porRio].map(([k, estacion]) => {
    const plano = sinAcentos(estacion.rio).toLowerCase()
    const delMapa = mapeados.filter((c) => claveCauce(c.nombre) === k).map((c) => c.nombre)
    return { estacion, nombres: [...new Set([...delMapa, estacion.rio, sinAcentos(estacion.rio), ...(OTROS_NOMBRES[plano] ?? [])])] }
  })
}

/** Decimales para mostrar un caudal: los esteros chicos necesitan dos. */
export const decimalesCaudal = (v: number): number => (v >= 100 ? 0 : v >= 10 ? 1 : 2)
