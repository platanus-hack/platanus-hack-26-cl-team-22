import { textoPosicion, type Riesgo } from './riesgo'
import type { Variable } from './types'

/**
 * Entrada guiada: primero el caso en palabras de la persona, después los criterios que ese caso pide
 * (con su peso y su rango aceptable) y por último el mapa.
 *
 * Dos clases de criterio, siempre a la vista como distintas:
 *  - simulados: los respalda una variable del modelo; su peso y su rango cambian el resultado;
 *  - de referencia: lo que ese caso además necesitaría medir. No tienen datos en esta versión,
 *    no entran al cálculo y no muestran ningún número.
 */
export type CasoId = 'hidro' | 'vivienda' | 'industria' | 'general'

export interface CriterioReferencia {
  id: string
  nombre: string
  que: string
  unidad?: string
}

export interface Caso {
  id: CasoId
  titulo: string
  /** palabras que delatan el caso en el texto libre */
  palabras: RegExp
  /** prioridad de 0 a 10 por id de variable; las que falten parten en 5 */
  prioridades: Record<string, number>
  referencia: readonly CriterioReferencia[]
  ejemplo: string
}

export const CASOS: readonly Caso[] = [
  {
    id: 'hidro',
    titulo: 'Energía hidráulica',
    // solo lo propio de una central: «agua» o «energía» a secas también las pide cualquier empresa
    palabras: /hidr|represa|embalse|turbina|caudal|central de pasada|minicentral|\brio\b/,
    prioridades: { pm25_anual: 0, seguridad: 5, crecimiento_poblacion: 8 },
    referencia: [
      { id: 'caudal', nombre: 'Caudal medio del río', que: 'Agua disponible para turbinar', unidad: 'm³/s' },
      { id: 'caida', nombre: 'Caída disponible', que: 'Desnivel entre la toma y la casa de máquinas', unidad: 'm' },
      { id: 'variabilidad', nombre: 'Variabilidad del caudal', que: 'Cuánto cambia entre años secos y lluviosos', unidad: '%' },
      { id: 'transmision', nombre: 'Distancia a la red de transmisión', que: 'Línea más cercana donde inyectar', unidad: 'km' },
    ],
    ejemplo: 'Quiero instalar una central hidroeléctrica de pasada y vender la energía a la red.',
  },
  {
    id: 'vivienda',
    titulo: 'Vivienda',
    palabras: /vivienda|casa|depart|depto|familia|hij|vivir|mudar|arriend|barrio|hogar/,
    prioridades: { pm25_anual: 8, seguridad: 8, crecimiento_poblacion: 3 },
    referencia: [
      { id: 'precio', nombre: 'Precio del suelo', que: 'Valor por metro cuadrado', unidad: 'UF/m²' },
      { id: 'viaje', nombre: 'Tiempo de viaje al trabajo', que: 'En transporte público, hora punta', unidad: 'min' },
      { id: 'servicios', nombre: 'Colegios y salud cerca', que: 'Establecimientos a distancia caminable' },
      { id: 'verde', nombre: 'Áreas verdes', que: 'Superficie por habitante', unidad: 'm²/hab' },
    ],
    ejemplo: 'Busco departamento para mi familia; mi hijo tiene asma.',
  },
  {
    id: 'industria',
    titulo: 'Industria y logística',
    palabras: /industr|planta|fabric|bodega|logist|distribu|manufact|empresa|galpon|comerci|local|negocio|centro de datos|data ?center|servidores|oficina|inver|instalar|energia|renovable|eolic|solar|central|mineria|agricol|proyecto/,
    prioridades: { pm25_anual: 3, seguridad: 5, crecimiento_poblacion: 8 },
    referencia: [
      { id: 'suelo', nombre: 'Suelo industrial disponible', que: 'Terrenos con uso de suelo permitido', unidad: 'ha' },
      { id: 'autopista', nombre: 'Acceso a autopistas', que: 'Distancia al enlace más cercano', unidad: 'km' },
      { id: 'energia', nombre: 'Energía y agua', que: 'Capacidad de conexión en el sector' },
      { id: 'trabajo', nombre: 'Mano de obra disponible', que: 'Población en edad de trabajar a 30 min' },
    ],
    ejemplo: 'Quiero abrir un centro de distribución y necesito que la zona gane población.',
  },
  {
    id: 'general',
    titulo: 'Evaluación general',
    palabras: /^$/,
    prioridades: { pm25_anual: 5, seguridad: 5, crecimiento_poblacion: 5 },
    referencia: [
      { id: 'precio', nombre: 'Costo del suelo', que: 'Valor por metro cuadrado', unidad: 'UF/m²' },
      { id: 'conectividad', nombre: 'Conectividad', que: 'Acceso a transporte y autopistas' },
    ],
    ejemplo: '',
  },
]

const GENERAL = CASOS[CASOS.length - 1]!

export function casoDe(id: CasoId): Caso {
  return CASOS.find((c) => c.id === id) ?? GENERAL
}

const sinTildes = (s: string) =>
  s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()

/**
 * Qué caso describe un texto libre, por palabras clave y en el orden de CASOS (el primero que calce).
 * Es una lectura simple y a la vista: la persona ve cómo se leyó su caso y puede cambiarlo.
 */
export function leerCaso(texto: string): CasoId {
  const t = sinTildes(texto)
  if (!t.trim()) return 'general'
  return (CASOS.find((c) => c.id !== 'general' && c.palabras.test(t)) ?? GENERAL).id
}

/* ---------- Modificar el requerimiento después del resumen ---------- */

export const LARGO_CAMBIO = 200

/** Qué palabras hablan de cada variable simulada. */
const TEMAS: readonly { id: string; palabras: RegExp }[] = [
  { id: 'pm25_anual', palabras: /aire|contamina|asma|respir|smog|humo|alergi/ },
  { id: 'seguridad', palabras: /segur|delit|robo|delincuen|asalto|de noche|nocturn/ },
  { id: 'crecimiento_poblacion', palabras: /crec|poblacion|clientes|demanda|habitantes/ },
]
const NADA = /no (me )?(importa|interesa|preocupa)|da igual|sin importar|ignora|quita/
const MENOS = /menos|baja|no tanto|no es tan/
const CLAVE = /clave|lo mas importante|sobre todo|principal|prioridad|mucho mas|fundamental|critic/

/**
 * Lectura sin modelo de lenguaje de un cambio escrito («ahora me importa más la seguridad y no el aire»):
 * por cada frase, la variable que nombra sube a «Mucho» o «Clave», o baja a «Poco» o «Nada» si la frase lo dice.
 * Devuelve las prioridades nuevas y qué variables cambió. Lo que no nombra queda como estaba.
 */
export function ajustarPorTexto(texto: string, prioridades: Readonly<Record<string, number>>): { prioridades: Record<string, number>; cambiadas: string[] } {
  const out = { ...prioridades }
  const cambiadas: string[] = []
  const frases = sinTildes(texto.slice(0, LARGO_CAMBIO * 4))
    .split(/[,.;:\n]| pero | y | aunque /)
    .map((f) => f.trim())
    .filter(Boolean)
  for (const f of frases) {
    const grado = NADA.test(f) ? 0 : MENOS.test(f) ? 3 : CLAVE.test(f) ? 10 : 8
    for (const t of TEMAS) {
      if (!(t.id in out) || !t.palabras.test(f)) continue
      if (out[t.id] !== grado) cambiadas.push(t.id)
      out[t.id] = grado
    }
  }
  return { prioridades: out, cambiadas: [...new Set(cambiadas)] }
}

/** El caso escrito antes más el cambio, acotado: es lo que lee Claude cuando el intermediario está. */
export function sumarCambio(contexto: string, cambio: string, max: number): string {
  const c = cambio.replace(/\s+/g, ' ').trim().slice(0, LARGO_CAMBIO)
  if (!c) return contexto
  const base = contexto.trim()
  return (base ? `${base.slice(0, Math.max(0, max - c.length - 1))}\n${c}` : c).slice(0, max)
}

/** Cinco grados en vez de una escala de once: menos que decidir. */
export const GRADOS: readonly { valor: number; texto: string }[] = [
  { valor: 0, texto: 'Nada' },
  { valor: 3, texto: 'Poco' },
  { valor: 5, texto: 'Medio' },
  { valor: 8, texto: 'Mucho' },
  { valor: 10, texto: 'Clave' },
]

/** Grado más cercano a una prioridad de 0 a 10. */
export function gradoDe(v: number): number {
  return GRADOS.reduce((m, g) => (Math.abs(g.valor - v) < Math.abs(m.valor - v) ? g : m)).valor
}

/** Prioridades de un caso solo para las variables que existen, ya en grados. */
export function prioridadesDe(caso: Caso, ids: readonly string[]): Record<string, number> {
  return Object.fromEntries(ids.map((id) => [id, gradoDe(caso.prioridades[id] ?? 5)]))
}

export const LARGO_CASO = 400
export const LARGO_CRITERIO = 40
export const MAX_PROPIOS = 3

/* ---------- Rangos: qué valor acepta la persona en cada variable simulada ---------- */

export interface OpcionRango {
  id: string
  titulo: string
  detalle?: string
  /** límite fijo en la unidad de la variable, o la parte de las comunas que debe quedar dentro (0 a 1) */
  limite: { valor: number } | { mejorFraccion: number } | null
}

const SIN_LIMITE: OpcionRango = { id: 'libre', titulo: 'Sin límite', detalle: 'Solo pesa en el índice.', limite: null }

/**
 * Rangos que se ofrecen por variable. Los del aire son referencias publicadas: la norma anual chilena
 * de PM2,5 (20 µg/m³) y la guía de la OMS de 2021 (5 µg/m³) con sus metas intermedias (10 y 15).
 * Los demás son cortes simples sobre los datos de la región.
 */
export const RANGOS: Record<string, readonly OpcionRango[]> = {
  pm25_anual: [
    SIN_LIMITE,
    { id: 'norma', titulo: 'Hasta 20 µg/m³', detalle: 'Norma anual chilena.', limite: { valor: 20 } },
    { id: 'oms-15', titulo: 'Hasta 15 µg/m³', detalle: 'Meta intermedia 3 de la OMS.', limite: { valor: 15 } },
    { id: 'oms-10', titulo: 'Hasta 10 µg/m³', detalle: 'Meta intermedia 4 de la OMS.', limite: { valor: 10 } },
    { id: 'oms-5', titulo: 'Hasta 5 µg/m³', detalle: 'Guía de la OMS (2021).', limite: { valor: 5 } },
  ],
  seguridad: [
    SIN_LIMITE,
    { id: 'mitad', titulo: 'Mitad más segura', detalle: 'Menos delitos que la mediana de la región.', limite: { mejorFraccion: 0.5 } },
    { id: 'tercio', titulo: 'Tercio más seguro', detalle: 'Entre las comunas con menos delitos.', limite: { mejorFraccion: 1 / 3 } },
  ],
  crecimiento_poblacion: [
    SIN_LIMITE,
    { id: 'no-pierde', titulo: 'Que no pierda población', detalle: '0 % o más frente a 2024.', limite: { valor: 0 } },
    { id: 'crece-5', titulo: 'Que crezca 5 % o más', detalle: 'Frente a 2024.', limite: { valor: 5 } },
  ],
}

export function rangosDe(variable: string): readonly OpcionRango[] {
  return RANGOS[variable] ?? [SIN_LIMITE]
}

/** Límite numérico de cada variable según el rango elegido y los valores del año; null = sin límite. */
export function resolverLimites(
  elegidos: Readonly<Record<string, string>>,
  variables: readonly Pick<Variable, 'id' | 'mejor'>[],
  valores: readonly Record<string, number | undefined>[],
): Record<string, number | null> {
  const out: Record<string, number | null> = {}
  for (const v of variables) {
    const op = rangosDe(v.id).find((o) => o.id === elegidos[v.id])
    if (!op || !op.limite) {
      out[v.id] = null
      continue
    }
    if ('valor' in op.limite) {
      out[v.id] = op.limite.valor
      continue
    }
    const xs = valores.map((f) => f[v.id]).filter((x): x is number => typeof x === 'number' && Number.isFinite(x))
    if (xs.length === 0) {
      out[v.id] = null
      continue
    }
    xs.sort((a, b) => (v.mejor === 'menor' ? a - b : b - a))
    out[v.id] = xs[Math.max(0, Math.ceil(xs.length * op.limite.mejorFraccion) - 1)]!
  }
  return out
}

/** Variables en que un valor queda fuera del rango aceptado. Sin dato no cuenta como fuera. */
export function fueraDeRango(
  valores: Readonly<Record<string, number | undefined>>,
  limites: Readonly<Record<string, number | null>>,
  variables: readonly Pick<Variable, 'id' | 'mejor'>[],
): string[] {
  const out: string[] = []
  for (const v of variables) {
    const lim = limites[v.id]
    const x = valores[v.id]
    if (lim === null || lim === undefined || x === undefined) continue
    if (v.mejor === 'menor' ? x > lim : x < lim) out.push(v.id)
  }
  return out
}

/** Nombre de un criterio propio: sin espacios de sobra y acotado; null si queda vacío o repetido. */
export function limpiarCriterio(texto: string, existentes: readonly string[]): string | null {
  const t = texto.replace(/\s+/g, ' ').trim().slice(0, LARGO_CRITERIO)
  if (!t) return null
  return existentes.some((e) => sinTildes(e) === sinTildes(t)) ? null : t
}

interface VarNombre {
  id: string
  nombre: string
}

/**
 * Explicación sin modelo de lenguaje: quién encabeza entre las comunas dentro de rango, en qué destaca
 * dentro de lo que la persona prioriza y quiénes siguen. Solo usa números del índice.
 */
export function explicar(
  riesgo: Riesgo,
  variables: readonly VarNombre[],
  pesos: Readonly<Record<string, number>>,
  nombre: (codigo: string) => string,
  o: { dentro?: ReadonlySet<string>; sinDatos?: readonly string[] } = {},
): string {
  const conIndice = riesgo.filas.filter((f) => f.indice !== null)
  const top = conIndice.filter((f) => !o.dentro || o.dentro.has(f.codigo)).slice(0, 3)
  const a = top[0]
  let t: string
  if (!a) {
    t = conIndice.length > 0 ? 'Ninguna comuna cumple todos tus rangos: prueba con uno más amplio.' : 'No hay datos suficientes para ordenar las comunas.'
  } else {
    // Se nombra aquello en que de verdad destaca (tercio mejor de la región); si en nada, lo que más pesa.
    const conPeso = variables.filter((v) => (pesos[v.id] ?? 0) > 0 && a.partes[v.id] !== undefined)
    const destaca = conPeso.filter((v) => a.partes[v.id]! <= 100 / 3)
    const clave = (destaca.length > 0 ? destaca : conPeso).sort((x, y) => (pesos[y.id] ?? 0) - (pesos[x.id] ?? 0) || a.partes[x.id]! - a.partes[y.id]!)[0]
    t = `${nombre(a.codigo)} es la de menor riesgo${o.dentro ? ' dentro de tus rangos' : ' para ti'}`
    if (clave) t += `: ${textoPosicion(a.partes[clave.id]!)} en ${clave.nombre.toLowerCase()}`
    t += '.'
    if (top.length === 3) t += ` Le siguen ${nombre(top[1]!.codigo)} y ${nombre(top[2]!.codigo)}.`
  }
  if (o.sinDatos && o.sinDatos.length > 0) t += ` Aún sin datos: ${o.sinDatos.map((s) => s.toLowerCase()).join(', ')}.`
  return t
}
