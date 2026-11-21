import type { OrigenAire } from './types'

export interface ResumenOrigen {
  /** parte del PM2,5 de la comuna que viene de sus propias emisiones; null si el dato no la trae */
  propia: number | null
  /** hasta `max` comunas de origen, de mayor a menor parte, sin la propia */
  otros: OrigenAire[]
  /** lo que no está en lo anterior: otras comunas y fondo regional */
  resto: number
}

/**
 * Elige qué mostrar del origen del aire de una comuna: su parte propia aparte,
 * las `max` comunas de origen más grandes y el resto. Ignora partes no positivas y suma las repetidas.
 */
export function seleccionarOrigenes(lista: readonly OrigenAire[] | undefined, comuna: string, max = 6): ResumenOrigen | null {
  if (!lista || lista.length === 0) return null
  const porOrigen = new Map<string, number>()
  for (const o of lista) {
    if (!(o.fraccion > 0)) continue
    porOrigen.set(o.origen, (porOrigen.get(o.origen) ?? 0) + o.fraccion)
  }
  if (porOrigen.size === 0) return null
  const propia = porOrigen.get(comuna) ?? null
  const otros = [...porOrigen.entries()]
    .filter(([origen]) => origen !== comuna)
    .map(([origen, fraccion]) => ({ origen, fraccion }))
    .sort((a, b) => b.fraccion - a.fraccion || a.origen.localeCompare(b.origen))
    .slice(0, Math.max(0, max))
  const usado = (propia ?? 0) + otros.reduce((s, o) => s + o.fraccion, 0)
  return { propia, otros, resto: Math.max(0, 1 - usado) }
}
