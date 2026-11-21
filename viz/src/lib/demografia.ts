/**
 * Open household model, run live in the browser for the moves lab.
 *
 * Mirrors experiments/validar_poblacion.py `proyectar` (Python is the reference; parity tests in
 * demografia.test.ts compare against projections exported with the parameters). Each year:
 *   flows[i][j] = pop[i] · out_rate[i] · shares[i][j]            (internal moves, j ≠ i)
 *   moved[i]    = pop[i] − Σ_j flows[i][j] + Σ_j flows[j][i]
 *   pop'[i]     = max(moved[i] + pop[i] · net[i], 0)
 *   net[i]      = births − deaths + arrivals from other regions + from abroad − departures,
 *                 each rate scaled by the user's multiplier (1 = measured value).
 * Pure functions only: no rendering, no randomness (flows are expected values).
 */

export const COMPONENTES = ['natalidad', 'mortalidad', 'llegan_regiones', 'llegan_extranjero', 'salen_regiones'] as const
export type Componente = (typeof COMPONENTES)[number]
export type Multiplicadores = Record<Componente, number>

export const MULTIPLICADORES_BASE: Multiplicadores = {
  natalidad: 1,
  mortalidad: 1,
  llegan_regiones: 1,
  llegan_extranjero: 1,
  salen_regiones: 1,
}

export interface Demografia {
  anios: number[]
  comunas: { codigo: string; nombre: string }[]
  poblacion_inicial: number[]
  tasa_salida: number[]
  destinos: number[][]
  tasas: Record<Componente, number[]>
  ine: { anios: number[]; poblacion: number[][] }
  referencia: { por_defecto: number[][]; cerrado: number[][] }
  supuestos: string[]
}

export interface Proyeccion {
  /** (años, comunas): población de cada año, la primera fila es la del censo. */
  poblacion: number[][]
  /** (años − 1, comunas, comunas): mudanzas internas de cada año simulado. */
  flujos: number[][][]
}

const esNumeros = (v: unknown, n: number): v is number[] =>
  Array.isArray(v) && v.length === n && v.every((x) => typeof x === 'number' && Number.isFinite(x))

/** Validates demografia.json at the boundary; throws with the name of what does not fit. */
export function leerDemografia(raw: unknown): Demografia {
  const r = raw as Record<string, any>
  const comunas = r?.comunas
  if (!Array.isArray(comunas) || comunas.length === 0) throw new Error('demografia.json: faltan las comunas')
  const n = comunas.length
  const anios = r.meta?.anios
  if (!esNumeros(anios, anios?.length ?? -1) || anios.length < 2) throw new Error('demografia.json: meta.anios no válido')
  if (!esNumeros(r.poblacion_inicial, n)) throw new Error('demografia.json: poblacion_inicial no calza con las comunas')
  if (!esNumeros(r.tasa_salida, n)) throw new Error('demografia.json: tasa_salida no calza con las comunas')
  if (!Array.isArray(r.destinos) || r.destinos.length !== n || !r.destinos.every((f: unknown) => esNumeros(f, n)))
    throw new Error('demografia.json: destinos debe ser una matriz de comunas × comunas')
  for (const c of COMPONENTES) if (!esNumeros(r.tasas?.[c], n)) throw new Error(`demografia.json: tasas.${c} no calza con las comunas`)
  const matriz = (m: unknown, filas: number) =>
    Array.isArray(m) && m.length === filas && m.every((f) => esNumeros(f, n)) ? (m as number[][]) : null
  const porDefecto = matriz(r.referencia?.por_defecto?.poblacion, anios.length)
  const cerrado = matriz(r.referencia?.cerrado?.poblacion, anios.length)
  if (!porDefecto || !cerrado) throw new Error('demografia.json: faltan las proyecciones de referencia')
  return {
    anios,
    comunas,
    poblacion_inicial: r.poblacion_inicial,
    tasa_salida: r.tasa_salida,
    destinos: r.destinos,
    tasas: r.tasas,
    ine: { anios: r.ine?.anios ?? [], poblacion: r.ine?.poblacion ?? [] },
    referencia: { por_defecto: porDefecto, cerrado },
    supuestos: Array.isArray(r.meta?.supuestos) ? r.meta.supuestos : [],
  }
}

export function proyectarDemografia(d: Demografia, m: Multiplicadores): Proyeccion {
  const n = d.comunas.length
  const neto = d.poblacion_inicial.map(
    (_, i) =>
      m.natalidad * d.tasas.natalidad[i]! -
      m.mortalidad * d.tasas.mortalidad[i]! +
      m.llegan_regiones * d.tasas.llegan_regiones[i]! +
      m.llegan_extranjero * d.tasas.llegan_extranjero[i]! -
      m.salen_regiones * d.tasas.salen_regiones[i]!,
  )
  const poblacion: number[][] = [d.poblacion_inicial.slice()]
  const flujos: number[][][] = []
  for (let t = 1; t < d.anios.length; t++) {
    const pop = poblacion[t - 1]!
    const f = pop.map((p, i) => d.destinos[i]!.map((s) => p * d.tasa_salida[i]! * s))
    const salen = f.map((fila) => fila.reduce((a, v) => a + v, 0))
    const llegan = new Array<number>(n).fill(0)
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) llegan[j]! += f[i]![j]!
    poblacion.push(pop.map((p, i) => Math.max(p - salen[i]! + llegan[i]! + p * neto[i]!, 0)))
    flujos.push(f)
  }
  return { poblacion, flujos }
}

/** The `k` largest moves between different comunas, largest first. */
export function mayoresFlujos(
  flujos: number[][],
  codigos: string[],
  k: number,
): { origen: string; destino: string; personas: number }[] {
  const todos: { origen: string; destino: string; personas: number }[] = []
  flujos.forEach((fila, i) =>
    fila.forEach((v, j) => {
      if (i !== j && v > 0) todos.push({ origen: codigos[i]!, destino: codigos[j]!, personas: v })
    }),
  )
  return todos.sort((a, b) => b.personas - a.personas).slice(0, k)
}
