import { punto, type Punto } from './data'
import type { Mejor, Simulacion } from './types'

export interface Diferencia {
  /** mediana del escenario activo menos mediana del escenario de referencia */
  delta: number
  activo: Punto
  base: Punto
}

export function diferencia(activo: Punto | undefined, base: Punto | undefined): Diferencia | undefined {
  if (!activo || !base) return undefined
  return { delta: activo.p50 - base.p50, activo, base }
}

/** Número de clases de la paleta divergente (--div-1 a --div-5). */
export const PASOS_DIV = 5

/** Redondea hacia arriba a un paso redondo (0,5 si es chico, 1 o 5 si es grande). Mínimo 0,5. */
export function techoRedondo(x: number): number {
  const v = Math.max(0.5, x)
  const paso = v <= 5 ? 0.5 : v <= 20 ? 1 : 5
  return Math.ceil(v / paso - 1e-9) * paso
}

/** Máximo |delta| entre comunas y años: da una escala simétrica fija mientras se mueve el año. */
export function maxAbsDiferencia(d: Simulacion, escenario: string, base: string, variable: string): number {
  let m = 0
  const a = d.trayectorias[escenario]
  const b = d.trayectorias[base]
  if (!a || !b) return techoRedondo(0)
  for (const [com, porVar] of Object.entries(a)) {
    const sa = porVar[variable]
    const sb = b[com]?.[variable]
    if (!sa || !sb) continue
    const n = Math.min(sa.p50.length, sb.p50.length)
    for (let i = 0; i < n; i++) m = Math.max(m, Math.abs(sa.p50[i]! - sb.p50[i]!))
  }
  return techoRedondo(m)
}

/**
 * Clase 0..4 de una diferencia en una escala simétrica [-max, +max].
 * 0 es la mayor mejora y 4 el mayor empeoramiento, según cuál dirección sea mejor.
 * La clase del medio (2) cubre el entorno del cero.
 */
export function claseDiferencia(delta: number, max: number, mejor: Mejor): number {
  const peor = mejor === 'menor' ? delta : -delta
  const t = max > 0 ? (peor + max) / (2 * max) : 0.5
  return Math.min(PASOS_DIV - 1, Math.max(0, Math.floor(t * PASOS_DIV)))
}

/** Bordes de las 5 clases, en unidades de la variable, de −max a +max. */
export function bordesDiferencia(max: number): number[] {
  return Array.from({ length: PASOS_DIV + 1 }, (_, i) => -max + (2 * max * i) / PASOS_DIV)
}

/** Diferencia de cada comuna para un año; solo las que tienen dato en ambos escenarios. */
export function diferenciasPorComuna(d: Simulacion, escenario: string, base: string, variable: string, idxAnio: number): Map<string, Diferencia> {
  const out = new Map<string, Diferencia>()
  for (const c of d.comunas) {
    const x = diferencia(punto(d, escenario, c.codigo, variable, idxAnio), punto(d, base, c.codigo, variable, idxAnio))
    if (x) out.set(c.codigo, x)
  }
  return out
}
