import type { Banda, Simulacion } from './types'

export function serie(d: Simulacion, escenario: string, comuna: string, variable: string): Banda | undefined {
  return d.trayectorias[escenario]?.[comuna]?.[variable]
}

export interface Punto {
  p10: number
  p50: number
  p90: number
}

export function punto(d: Simulacion, escenario: string, comuna: string, variable: string, idxAnio: number): Punto | undefined {
  const s = serie(d, escenario, comuna, variable)
  if (!s) return undefined
  const p10 = s.p10[idxAnio]
  const p50 = s.p50[idxAnio]
  const p90 = s.p90[idxAnio]
  if (p10 === undefined || p50 === undefined || p90 === undefined) return undefined
  return { p10, p50, p90 }
}

/** Variables que tienen al menos una serie en trayectorias. */
export function variablesConDato(d: Simulacion): Set<string> {
  const out = new Set<string>()
  for (const porComuna of Object.values(d.trayectorias)) {
    for (const porVar of Object.values(porComuna)) for (const v of Object.keys(porVar)) out.add(v)
  }
  return out
}

/** Rango [min, max] de la mediana de una variable en todos los escenarios, comunas y años. */
export function dominio(d: Simulacion, variable: string): [number, number] {
  let lo = Infinity
  let hi = -Infinity
  for (const porComuna of Object.values(d.trayectorias)) {
    for (const porVar of Object.values(porComuna)) {
      const s = porVar[variable]
      if (!s) continue
      for (const v of s.p50) {
        if (v < lo) lo = v
        if (v > hi) hi = v
      }
    }
  }
  if (!Number.isFinite(lo)) return [0, 1]
  if (lo === hi) return [lo - 1, hi + 1]
  return [Math.floor(lo), Math.ceil(hi)]
}
