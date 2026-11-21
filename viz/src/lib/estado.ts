import { fmt } from './format'

/**
 * Veredicto directo de una comuna frente a la norma anual, con las categorías de la ley chilena
 * (Ley 19.300): sobre la norma es zona saturada; entre el 80 % y el 100 %, zona latente.
 */
export type Estado = 'riesgo' | 'limite' | 'cumple'

export const FRACCION_LATENTE = 0.8

export const TEXTO_ESTADO: Record<Estado, string> = {
  riesgo: 'En riesgo',
  limite: 'Al límite',
  cumple: 'Cumple la norma',
}

/** Un valor igual a la norma todavía no la supera. */
export function estadoAire(v: number, norma: number): Estado {
  if (v > norma) return 'riesgo'
  if (v >= norma * FRACCION_LATENTE) return 'limite'
  return 'cumple'
}

export interface Veredicto {
  estado: Estado
  titulo: string
  /** por qué: distancia a la norma, en una frase corta */
  razon: string
  /** hacia dónde va al final de la proyección; null si no hay más años que mirar */
  futuro: string | null
}

/** Cambio de la mediana bajo el cual la proyección cuenta como "sin cambio". */
export const SIN_CAMBIO = 0.3

/**
 * Veredicto de una comuna en el año elegido y lo que dice la proyección para el último año.
 * Usa la mediana; `banda` (p10 y p90 del año elegido) solo matiza si la banda cruza la norma.
 */
export function veredictoComuna(
  p50: readonly number[],
  anios: readonly number[],
  idx: number,
  norma: number,
  banda?: { p10: number; p90: number },
): Veredicto | null {
  const v = p50[idx]
  if (v === undefined || !Number.isFinite(v) || !(norma > 0)) return null
  const estado = estadoAire(v, norma)
  const n = fmt(norma, Number.isInteger(norma) ? 0 : 1)
  let razon =
    estado === 'riesgo' ? `${fmt(v - norma, 1)} sobre la norma de ${n}` : estado === 'limite' ? `a ${fmt(norma - v, 1)} de la norma de ${n}` : `${fmt(norma - v, 1)} bajo la norma de ${n}`
  if (banda && estado !== 'riesgo' && banda.p90 > norma) razon += '; la banda la supera'
  if (banda && estado === 'riesgo' && banda.p10 <= norma) razon += '; la banda llega a cumplirla'

  const ult = p50.length - 1
  let futuro: string | null = null
  if (idx < ult && anios.length === p50.length) {
    const fin = p50[ult]!
    const aFin = anios[ult]!
    const eFin = estadoAire(fin, norma)
    const d = fin - v
    if (estado === 'riesgo' && eFin !== 'riesgo') {
      const i = p50.findIndex((x, k) => k > idx && x <= norma)
      futuro = `Sale del riesgo en ${anios[i]}`
    } else if (estado !== 'riesgo' && eFin === 'riesgo') {
      const i = p50.findIndex((x, k) => k > idx && x > norma)
      futuro = `Entra en riesgo en ${anios[i]}`
    } else if (estado === 'riesgo') {
      futuro = d < -SIN_CAMBIO ? `Mejora, pero en ${aFin} sigue en riesgo` : d > SIN_CAMBIO ? `Empeora: en ${aFin} sigue en riesgo` : `No cambia: en ${aFin} sigue en riesgo`
    } else {
      const sigue = eFin === 'limite' ? 'sigue al límite' : 'sigue cumpliendo'
      futuro = d < -SIN_CAMBIO ? `Mejora: en ${aFin} ${sigue}` : d > SIN_CAMBIO ? `Empeora, pero en ${aFin} ${sigue}` : `No cambia: en ${aFin} ${sigue}`
    }
  }
  return { estado, titulo: TEXTO_ESTADO[estado], razon, futuro }
}
