import type { Punto } from './data'
import { cruceBanda, nivel, type Cruce } from './niveles'

/** Número de papeles fríos para políticas (--pol-0 a --pol-4); se repiten en orden. */
export const PAPELES_POLITICA = 5

/** Hash determinista de un texto a [0, 1). */
export function hash01(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return ((h >>> 0) % 100000) / 100000
}

export interface AportePolitica {
  politicaId: string
  /** índice de la política en el orden del archivo: fija su papel y su lugar en la pila */
  indice: number
  /** cambio de la mediana final que se le atribuye; se usa su valor absoluto */
  delta: number
}

export interface Labio {
  politicaId: string
  indice: number
  /** ancho del borde de esta hoja que asoma bajo la comuna (unidades de mundo) */
  ancho: number
  /** corrimiento hacia abajo y a la derecha de esta hoja respecto de la comuna */
  corrimiento: number
  pegada: boolean
}

/**
 * Pila de hojas de política bajo una comuna, vista por su canto. Cada política con aporte es una copia
 * del contorno de la comuna, corrida hacia abajo y a la derecha: lo que asoma (el labio) es proporcional
 * a su aporte, entre `min` y `max`, y las hojas se apilan en el orden de las políticas.
 * Las despegadas conservan su lugar en la pila completa, para salir desde donde estaban; las pegadas
 * se apilan solo entre ellas, así no quedan huecos.
 */
export function apilarLabios(
  aportes: readonly AportePolitica[],
  activas: ReadonlySet<string>,
  deltaMax: number,
  min: number,
  max: number,
): Labio[] {
  const validos = aportes.filter((a) => Number.isFinite(a.delta) && Math.abs(a.delta) > 0).sort((a, b) => a.indice - b.indice)
  const escala = deltaMax > 0 ? deltaMax : 1
  let pegado = 0
  let total = 0
  return validos.map((a) => {
    const ancho = Math.min(max, Math.max(min, (max * Math.abs(a.delta)) / escala))
    const pegada = activas.has(a.politicaId)
    total += ancho
    if (pegada) pegado += ancho
    return { politicaId: a.politicaId, indice: a.indice, ancho, corrimiento: pegada ? pegado : total, pegada }
  })
}

export interface Pila {
  /** nivel del papel de fondo; null = sin dato (papel base sin cortar) */
  nivel: number | null
  cruce: Cruce | null
}

/** Capas de nivel de una comuna para un punto proyectado. */
export function apilarNivel(p: Punto | undefined, cortes: readonly number[]): Pila {
  if (!p) return { nivel: null, cruce: null }
  return { nivel: nivel(p.p50, cortes), cruce: cruceBanda(p, cortes) }
}
