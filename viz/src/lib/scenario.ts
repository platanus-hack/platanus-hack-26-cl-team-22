import type { Escenario } from './types'

export function mismoConjunto(a: readonly string[], b: readonly string[]): boolean {
  const sa = new Set(a)
  const sb = new Set(b)
  if (sa.size !== sb.size) return false
  for (const x of sa) if (!sb.has(x)) return false
  return true
}

/** Lectura de la credibilidad de un escenario; sin campo, la lectura por defecto. */
export function lecturaDe(e: Escenario, defecto?: string): string | undefined {
  return e.lectura ?? defecto
}

/**
 * Escenario cuyas políticas activas coinciden exactamente con el conjunto y, si se pide
 * (o hay lectura por defecto), con la lectura de la credibilidad; null si no hay.
 */
export function buscarEscenario(
  escenarios: readonly Escenario[],
  activas: ReadonlySet<string>,
  lectura?: string,
  defecto?: string,
): Escenario | null {
  const lista = [...activas]
  const objetivo = lectura ?? defecto
  return (
    escenarios.find((e) => mismoConjunto(e.politicas_activas, lista) && (objetivo === undefined || lecturaDe(e, defecto) === objetivo)) ?? null
  )
}

export interface Seleccion {
  escenario: Escenario
  /** false si la combinación pedida no está calculada y se conserva el último escenario válido */
  calculada: boolean
}

export function resolverSeleccion(
  escenarios: readonly Escenario[],
  activas: ReadonlySet<string>,
  ultimo: Escenario,
  lectura?: string,
  defecto?: string,
): Seleccion {
  const e = buscarEscenario(escenarios, activas, lectura, defecto)
  return e ? { escenario: e, calculada: true } : { escenario: ultimo, calculada: false }
}

/** Escenario de partida: "base" si existe, si no el que tiene más políticas activas. */
export function escenarioInicial(escenarios: readonly Escenario[]): Escenario {
  const base = escenarios.find((e) => e.id === 'base')
  if (base) return base
  return [...escenarios].sort((a, b) => b.politicas_activas.length - a.politicas_activas.length)[0] ?? escenarios[0]!
}

/** Lecturas presentes en los escenarios, con la de defecto primero. Vacía si ninguno declara lectura. */
export function lecturasDisponibles(escenarios: readonly Escenario[], defecto?: string): string[] {
  const s = new Set<string>()
  for (const e of escenarios) if (e.lectura) s.add(e.lectura)
  if (s.size === 0) return []
  const out = [...s]
  if (defecto && s.has(defecto)) return [defecto, ...out.filter((x) => x !== defecto)]
  return out
}

export function alternar(activas: ReadonlySet<string>, id: string): Set<string> {
  const n = new Set(activas)
  if (n.has(id)) n.delete(id)
  else n.add(id)
  return n
}
