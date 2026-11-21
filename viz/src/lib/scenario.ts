import type { Escenario } from './types'

export function mismoConjunto(a: readonly string[], b: readonly string[]): boolean {
  const sa = new Set(a)
  const sb = new Set(b)
  if (sa.size !== sb.size) return false
  for (const x of sa) if (!sb.has(x)) return false
  return true
}

/** Escenario cuyas políticas activas coinciden exactamente con el conjunto; null si no hay. */
export function buscarEscenario(escenarios: readonly Escenario[], activas: ReadonlySet<string>): Escenario | null {
  const lista = [...activas]
  return escenarios.find((e) => mismoConjunto(e.politicas_activas, lista)) ?? null
}

export interface Seleccion {
  escenario: Escenario
  /** false si la combinación pedida no está calculada y se conserva el último escenario válido */
  calculada: boolean
}

export function resolverSeleccion(escenarios: readonly Escenario[], activas: ReadonlySet<string>, ultimo: Escenario): Seleccion {
  const e = buscarEscenario(escenarios, activas)
  return e ? { escenario: e, calculada: true } : { escenario: ultimo, calculada: false }
}

/** Escenario de partida: "base" si existe, si no el que tiene más políticas activas. */
export function escenarioInicial(escenarios: readonly Escenario[]): Escenario {
  const base = escenarios.find((e) => e.id === 'base')
  if (base) return base
  return [...escenarios].sort((a, b) => b.politicas_activas.length - a.politicas_activas.length)[0] ?? escenarios[0]!
}

export function alternar(activas: ReadonlySet<string>, id: string): Set<string> {
  const n = new Set(activas)
  if (n.has(id)) n.delete(id)
  else n.add(id)
  return n
}
