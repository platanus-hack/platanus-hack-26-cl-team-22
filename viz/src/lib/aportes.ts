/**
 * Lo que hay detrás de dos indicadores de una comuna, ítem por ítem (issue #36):
 * - proyectos SEIA aprobados (datos/inversion_proyectos.json): cada uno suma 1 a «inversión evaluada»;
 * - licitaciones 2024 (datos/licitaciones/<codigo>.json): cuánto movió cada una la credibilidad municipal.
 * Son archivos externos: se validan campo por campo y lo que no calza se descarta.
 */

type Obj = Record<string, unknown>
const esObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)
const esNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const texto = (v: unknown, max: number): string => (typeof v === 'string' ? v.replace(/\s+/g, ' ').trim().slice(0, max) : '')
const numONull = (v: unknown, max = 1e15): number | null => (esNum(v) && v >= 0 && v < max ? v : null)

export interface ProyectoSeia {
  id: string
  nombre: string
  titular: string
  tipo: string
  /** millones de dólares; null si la ficha no lo trae */
  monto: number | null
  fecha: string
  /** ficha pública en seia.sea.gob.cl; null si la dirección no es de ese sitio */
  url: string | null
}

/** Solo fichas del SEIA por https: nunca se enlaza a otro sitio aunque el archivo lo traiga. */
export function urlSeia(raw: unknown): string | null {
  if (typeof raw !== 'string') return null
  try {
    const u = new URL(raw.trim())
    return u.protocol === 'https:' && u.hostname === 'seia.sea.gob.cl' ? u.href : null
  } catch {
    return null
  }
}

const MAX_ITEMS = 2000

/** Proyectos SEIA de una comuna, del más reciente al más antiguo. null si el archivo no sirve o no trae la comuna. */
export function leerProyectos(raw: unknown, codigo: string): ProyectoSeia[] | null {
  if (!esObj(raw) || !Array.isArray(raw.comunas)) return null
  const c = raw.comunas.find((x) => esObj(x) && x.codigo === codigo)
  if (!esObj(c) || !Array.isArray(c.proyectos)) return null
  const out: ProyectoSeia[] = []
  for (const p of c.proyectos.slice(0, MAX_ITEMS)) {
    if (!esObj(p)) continue
    const nombre = texto(p.nombre, 160)
    const id = texto(p.expediente_id, 20)
    if (!nombre || !/^\d{1,20}$/.test(id)) continue
    const fecha = texto(p.fecha_presentacion, 10)
    out.push({
      id,
      nombre,
      titular: texto(p.titular, 90),
      tipo: texto(p.descripcion_tipologia, 70),
      monto: numONull(p.inversion_musd, 1e6),
      fecha: /^\d{4}-\d{2}-\d{2}$/.test(fecha) ? fecha : '',
      url: urlSeia(p.url_ficha),
    })
  }
  return out.sort((a, b) => b.fecha.localeCompare(a.fecha))
}

export type EstadoLicitacion = 'adjudicada' | 'fallida' | 'abierta'
const ESTADOS: readonly EstadoLicitacion[] = ['adjudicada', 'fallida', 'abierta']
export const TEXTO_ESTADO_LICITACION: Record<EstadoLicitacion, string> = { adjudicada: 'Adjudicada', fallida: 'Fallida', abierta: 'Abierta' }

export interface Licitacion {
  codigo: string
  nombre: string
  estado: EstadoLicitacion
  sector: string
  /** pesos chilenos */
  estimado: number | null
  adjudicado: number | null
  oferentes: number | null
  /** cambio en la credibilidad municipal (escala 0 a 1) por esta licitación; 0 si no entra al modelo */
  aporte: number
}

export interface LicitacionesComuna {
  anio: number
  /** la comuna usa las licitaciones en el modelo (hoy, las cinco con más delitos) */
  afectaModelo: boolean
  /** credibilidad municipal, 0 a 1; null si la comuna no entra al modelo */
  credibilidad: number | null
  tasaAdjudicacion: number | null
  /** tope de licitaciones efectivas que pesa el modelo */
  tope: number | null
  conteo: Record<EstadoLicitacion, number>
  licitaciones: Licitacion[]
}

/** Licitaciones de una comuna (datos/licitaciones/<codigo>.json). null si el archivo no sirve. */
export function leerLicitaciones(raw: unknown): LicitacionesComuna | null {
  if (!esObj(raw) || !Array.isArray(raw.licitaciones)) return null
  const licitaciones: Licitacion[] = []
  const conteo: Record<EstadoLicitacion, number> = { adjudicada: 0, fallida: 0, abierta: 0 }
  for (const l of raw.licitaciones.slice(0, MAX_ITEMS)) {
    if (!esObj(l)) continue
    const nombre = texto(l.nombre, 140)
    const estado = l.estado
    if (!nombre || typeof estado !== 'string' || !(ESTADOS as readonly string[]).includes(estado)) continue
    const e = estado as EstadoLicitacion
    conteo[e]++
    licitaciones.push({
      codigo: texto(l.codigo_externo, 30),
      nombre,
      estado: e,
      sector: texto(l.sector, 40),
      // un monto en cero es «sin monto»: una fallida no adjudicó nada
      estimado: numONull(l.monto_estimado_clp) || null,
      adjudicado: numONull(l.monto_adjudicado_clp) || null,
      oferentes: numONull(l.numero_oferentes, 1e4),
      aporte: esNum(l.aporte_credibilidad) && Math.abs(l.aporte_credibilidad) <= 1 ? l.aporte_credibilidad : 0,
    })
  }
  const fraccion = (v: unknown) => (esNum(v) && v >= 0 && v <= 1 ? v : null)
  return {
    anio: esNum(raw.anio) && raw.anio > 2000 && raw.anio < 2100 ? raw.anio : 2024,
    afectaModelo: raw.afecta_modelo === true,
    credibilidad: fraccion(raw.credibilidad_media),
    tasaAdjudicacion: fraccion(raw.tasa_adjudicacion),
    tope: esNum(raw.max_n_efectivo) && raw.max_n_efectivo > 0 ? raw.max_n_efectivo : null,
    conteo,
    licitaciones,
  }
}

/** Monto que se muestra y por el que se ordena: lo adjudicado y, si no hay, lo estimado. */
export function montoDe(l: Licitacion): number | null {
  return l.adjudicado ?? l.estimado
}

export type OrdenLicitacion = 'monto' | 'aporte'

/**
 * Filtra por estado (null = todas) y ordena de mayor a menor; lo que no tiene monto va al final.
 * Por aporte manda el tamaño del efecto (con o sin signo) y, a igual aporte, el monto.
 */
export function filtrarLicitaciones(ls: readonly Licitacion[], estado: EstadoLicitacion | null, orden: OrdenLicitacion): Licitacion[] {
  const monto = (l: Licitacion) => montoDe(l) ?? -1
  const clave = (l: Licitacion) => (orden === 'monto' ? monto(l) : Math.abs(l.aporte))
  return ls
    .filter((l) => !estado || l.estado === estado)
    .sort((a, b) => clave(b) - clave(a) || monto(b) - monto(a) || a.nombre.localeCompare(b.nombre))
}

/** Por aporte cuando la comuna entra al modelo; fuera de él todas aportan 0 y se ordena por monto. */
export function ordenInicial(afectaModelo: boolean): OrdenLicitacion {
  return afectaModelo ? 'aporte' : 'monto'
}

/** Credibilidad de la comuna sin esa licitación (0 a 1); null si no la movió o la comuna no entra al modelo. */
export function credibilidadSin(c: LicitacionesComuna, l: Licitacion): number | null {
  return c.afectaModelo && c.credibilidad !== null && l.aporte !== 0 ? c.credibilidad - l.aporte : null
}

/** Aporte a la credibilidad en puntos de una escala de 0 a 100, con signo. */
export function puntosCredibilidad(aporte: number, fmt: (n: number, d?: number) => string): string {
  return `${aporte > 0 ? '+' : aporte < 0 ? '−' : ''}${fmt(Math.abs(aporte) * 100, 3)} pt`
}

/** Aporte de una licitación de cada estado: dentro de una comuna todas las de un estado aportan lo mismo. */
export function aportePorEstado(c: LicitacionesComuna): Partial<Record<EstadoLicitacion, number>> {
  const out: Partial<Record<EstadoLicitacion, number>> = {}
  for (const l of c.licitaciones) if (out[l.estado] === undefined) out[l.estado] = l.aporte
  return out
}

/** Página `n` (desde 0) de una lista y cuántas páginas hay. */
export function pagina<T>(xs: readonly T[], n: number, porPagina: number): { filas: T[]; paginas: number; actual: number } {
  const paginas = Math.max(1, Math.ceil(xs.length / porPagina))
  const actual = Math.min(Math.max(0, n), paginas - 1)
  return { filas: xs.slice(actual * porPagina, (actual + 1) * porPagina), paginas, actual }
}

/** «$ 1.250 millones», «$ 5,1 millones» o «$ 850 mil»: pesos chilenos en la escala que se lee de un vistazo. */
export function pesosCortos(v: number | null, fmt: (n: number, d?: number) => string): string {
  if (v === null) return 'sin monto'
  if (v >= 1e9) return `$ ${fmt(v / 1e6, 0)} millones`
  if (v >= 1e6) return `$ ${fmt(v / 1e6, 1)} millones`
  if (v >= 1e3) return `$ ${fmt(v / 1e3, 0)} mil`
  return `$ ${fmt(v, 0)}`
}
