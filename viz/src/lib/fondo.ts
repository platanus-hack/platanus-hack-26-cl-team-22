import { apilarNivel } from './capas'
import type { Punto } from './data'
import type { Diferencia } from './diferencia'
import type { Lena } from './lena'
import { papelNivel, pasoDiferencia } from './niveles'
import type { Mejor } from './types'

export type ModoMapa = 'valor' | 'diferencia' | 'lena' | 'agua'

export interface DatosFondo {
  modo: ModoMapa
  cortes: readonly number[]
  puntos: ReadonlyMap<string, Punto>
  difs: ReadonlyMap<string, Diferencia> | null
  difMax: number
  mejor: Mejor
  lena: Lena | null
  /** modo agua: comunas por donde pasa el río elegido */
  pasa?: ReadonlySet<string>
}

/**
 * Clase de color de una comuna según lo que muestra el mapa: nivel, diferencia o zona de leña.
 * `codigo` es el del polígono; `sim`, el de la simulación (undefined = sin dato).
 */
export function claseFondo(d: DatosFondo, codigo: string, sim: string | undefined): string {
  // El mapa del agua deja ver el relieve: mandan los ríos, y solo se tiñen las comunas por donde pasa el elegido.
  if (d.modo === 'agua') return d.pasa?.has(codigo) ? 'mejora-1' : 'sin-dato'
  if (d.modo === 'lena') {
    const z = d.lena?.comunas.find((c) => c.codigo === codigo)?.zona
    return z === 'A' ? 'zona-a' : z === 'B' ? 'zona-b' : 'sin-dato'
  }
  if (!sim) return 'sin-dato'
  if (d.modo === 'diferencia') {
    const dif = d.difs?.get(sim)
    if (!dif) return 'sin-dato'
    const s = pasoDiferencia(dif.delta, d.difMax, d.mejor)
    return s === 0 ? 'dif-0' : s < 0 ? `mejora-${-s}` : `empeora-${s}`
  }
  const n = apilarNivel(d.puntos.get(sim), d.cortes).nivel
  return n === null ? 'sin-dato' : `nivel-${papelNivel(n, d.cortes)}`
}

/** Variable CSS del papel de una clase de fondo; null si la comuna no lleva color (sin dato). */
export function variableDeClase(clase: string): string | null {
  if (clase === 'sin-dato') return null
  if (clase === 'dif-0') return '--papel'
  return `--${clase}`
}
