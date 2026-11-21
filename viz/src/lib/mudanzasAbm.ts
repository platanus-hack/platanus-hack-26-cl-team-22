/**
 * Agent-based moves simulation: saturation and spill (docs/modelo-mudanzas-abm.md).
 *
 * Agents are groups of `tamanoGrupo` persons. Every year, on the start-of-year state:
 *   1. capacity grows with building permits;
 *   2. one categorical draw per agent: dies / leaves the region / seeks an internal move / stays;
 *   3. births (Poisson) as local groups in their comuna (they may overfill it);
 *   4. arrivals from other regions and from abroad (Poisson);
 *   5. everyone seeking a destination, in random order, picks a comuna with room by weight:
 *      internal from i → observed shares destinos[i][j]; from other regions → measured geography;
 *      from abroad → measured geography ('fijo') or (foreign stock + 1)^phi ('redes'). Each
 *      arrival from abroad raises its comuna's stock: the network feedback. A full comuna drops
 *      out of the draw (spill); with no room anywhere the demand is unmet.
 * With infinite capacity and 'fijo', every component's expected value equals the deterministic
 * model of demografia.ts (parity tests in mudanzasAbm.test.ts). Pure functions, seeded PRNG.
 */
import { MULTIPLICADORES_BASE, leerDemografia, type Demografia, type Multiplicadores } from './demografia'
import { crearPrng, type Prng } from './prng'

export interface ParametrosAbm extends Demografia {
  /** Housing capacity per comuna in persons; absent = infinite. */
  capacidad_inicial?: number[]
  /** New dwellings per year (building permits). Needs `personas_por_vivienda`. */
  permisos_anuales?: number[]
  personas_por_vivienda?: number[]
  /** Foreign-born persons living in each comuna at the start. */
  stock_extranjero?: number[]
  /** Network exponent of the 'redes' rule (fitted in experiments/validar_redes.py). */
  phi?: number
}

export type Evento =
  | { tipo: 'ola_migratoria'; desde: number; anios: number; m: number }
  | { tipo: 'densificar'; comuna: number; desde: number; m: number }
  | { tipo: 'crisis'; desde: number; anios: number; m: number }

export interface OpcionesAbm {
  semilla: number
  tamanoGrupo?: number
  modoExtranjero: 'fijo' | 'redes'
  multiplicadores?: Multiplicadores
  eventos?: Evento[]
}

export interface ResultadoAbm {
  /** (years, comunas) persons. */
  poblacion: number[][]
  /** (years, comunas) capacity in persons; Infinity when capacity is not limited. */
  capacidad: number[][]
  /** (years, comunas) persons / capacity; null when capacity is not limited. */
  ocupacion: (number | null)[][]
  /** Per simulated year: internal moves between comunas (indices) in persons. */
  flujos: { origen: number; destino: number; personas: number }[][]
  nacimientos: number[][]
  defunciones: number[][]
  llegadasExtranjero: number[][]
  llegadasRegiones: number[][]
  /** Persons who left the region from each comuna. */
  salidasRegion: number[][]
  /** Comunas (indices) without room for one more group at the end of the year. */
  saturadas: number[][]
  /** Groups whose preferred destination was full and went elsewhere. */
  derrames: number[]
  /** Groups that found no room anywhere (internal ones stayed, external ones did not come). */
  noAtendida: number[]
}

const ORIGEN_INTERNO = 0
const ORIGEN_REGION = 1
const ORIGEN_EXTRANJERO = 2

/** Reads demografia.json including its `abm` block (capacity, permits, foreign stock, phi). */
export function leerParametrosAbm(raw: unknown): ParametrosAbm {
  const d = leerDemografia(raw)
  const abm = (raw as { abm?: Record<string, unknown> })?.abm
  const n = d.comunas.length
  const vector = (v: unknown) =>
    Array.isArray(v) && v.length === n && v.every((x) => typeof x === 'number' && Number.isFinite(x)) ? (v as number[]) : undefined
  return {
    ...d,
    capacidad_inicial: vector(abm?.capacidad_inicial),
    permisos_anuales: vector(abm?.permisos_anuales),
    personas_por_vivienda: vector(abm?.personas_por_vivienda),
    stock_extranjero: vector(abm?.stock_extranjero),
    phi: typeof abm?.phi === 'number' ? abm.phi : undefined,
  }
}

function factor(eventos: Evento[], tipo: 'ola_migratoria' | 'crisis', anio: number): number {
  let m = 1
  for (const e of eventos) if (e.tipo === tipo && anio >= e.desde && anio < e.desde + e.anios) m *= e.m
  return m
}

export function simular(p: ParametrosAbm, o: OpcionesAbm): ResultadoAbm {
  const n = p.comunas.length
  const tamano = o.tamanoGrupo ?? 250
  const mult = o.multiplicadores ?? MULTIPLICADORES_BASE
  const eventos = o.eventos ?? []
  const phi = p.phi ?? 1
  if (p.permisos_anuales && !p.personas_por_vivienda)
    throw new Error('permisos_anuales needs personas_por_vivienda to turn dwellings into persons')
  const rng: Prng = crearPrng(o.semilla)
  const limitada = !!p.capacidad_inicial

  // Agents: one entry per group, holding its comuna index.
  let agentes: number[] = []
  p.poblacion_inicial.forEach((pob, i) => {
    for (let k = Math.round(pob / tamano); k > 0; k--) agentes.push(i)
  })
  const capacidad = limitada ? p.capacidad_inicial!.slice() : new Array<number>(n).fill(Infinity)
  const stock = (p.stock_extranjero ?? new Array<number>(n).fill(0)).slice()

  const contar = (xs: number[]) => {
    const c = new Array<number>(n).fill(0)
    for (const i of xs) c[i]!++
    return c
  }
  const personas = (grupos: number[]) => grupos.map((g) => g * tamano)
  const ocupacionDe = (pob: number[], cap: number[]) => pob.map((v, j) => (limitada ? v / cap[j]! : null))

  const r: ResultadoAbm = {
    poblacion: [personas(contar(agentes))],
    capacidad: [capacidad.slice()],
    ocupacion: [],
    flujos: [],
    nacimientos: [],
    defunciones: [],
    llegadasExtranjero: [],
    llegadasRegiones: [],
    salidasRegion: [],
    saturadas: [],
    derrames: [],
    noAtendida: [],
  }
  r.ocupacion.push(ocupacionDe(r.poblacion[0]!, capacidad))

  const pesos = new Float64Array(n)
  for (let t = 0; t + 1 < p.anios.length; t++) {
    const anio = p.anios[t]!
    const crisis = factor(eventos, 'crisis', anio)
    const ola = factor(eventos, 'ola_migratoria', anio)

    // 1. Capacity grows with building permits.
    if (limitada && p.permisos_anuales) {
      for (let j = 0; j < n; j++) {
        let m = 1
        for (const e of eventos) if (e.tipo === 'densificar' && e.comuna === j && anio >= e.desde) m *= e.m
        capacidad[j]! += p.permisos_anuales[j]! * p.personas_por_vivienda![j]! * m
      }
    }

    // Start-of-year state.
    const P = personas(contar(agentes))
    const ocupadas = P.slice()
    const defunciones = new Array<number>(n).fill(0)
    const salidas = new Array<number>(n).fill(0)

    // 2. One draw per agent: dies / leaves the region / seeks a move / stays.
    const quedan: number[] = []
    const buscan: { origen: number; tipo: number }[] = []
    for (const i of agentes) {
      const pm = mult.mortalidad * p.tasas.mortalidad[i]!
      const ps = mult.salen_regiones * p.tasas.salen_regiones[i]!
      const pb = Math.min(1, crisis * p.tasa_salida[i]!)
      const u = rng.uniform()
      if (u < pm) {
        defunciones[i]! += tamano
        ocupadas[i]! -= tamano
      } else if (u < pm + ps) {
        salidas[i]! += tamano
        ocupadas[i]! -= tamano
      } else if (u < pm + ps + pb) {
        buscan.push({ origen: i, tipo: ORIGEN_INTERNO })
      } else {
        quedan.push(i)
      }
    }

    // 3. Births: local groups in their comuna, even if it is full.
    const nacimientos = new Array<number>(n).fill(0)
    for (let i = 0; i < n; i++) {
      const g = rng.poisson((mult.natalidad * p.tasas.natalidad[i]! * P[i]!) / tamano)
      for (let k = 0; k < g; k++) quedan.push(i)
      nacimientos[i] = g * tamano
      ocupadas[i]! += g * tamano
    }

    // 4. Arrivals from outside the region.
    let lambdaReg = 0
    let lambdaExt = 0
    for (let j = 0; j < n; j++) {
      lambdaReg += p.tasas.llegan_regiones[j]! * P[j]!
      lambdaExt += p.tasas.llegan_extranjero[j]! * P[j]!
    }
    const nReg = rng.poisson((mult.llegan_regiones * crisis * lambdaReg) / tamano)
    const nExt = rng.poisson((mult.llegan_extranjero * crisis * ola * lambdaExt) / tamano)
    for (let k = 0; k < nReg; k++) buscan.push({ origen: -1, tipo: ORIGEN_REGION })
    for (let k = 0; k < nExt; k++) buscan.push({ origen: -1, tipo: ORIGEN_EXTRANJERO })

    // 5. Destinations, in random order. An internal mover keeps its place until it settles
    //    elsewhere, so a failed search never pushes its comuna over capacity.
    const orden = buscan.map((_, k) => k)
    rng.barajar(orden)
    const flujo = new Map<number, number>()
    const llegReg = new Array<number>(n).fill(0)
    const llegExt = new Array<number>(n).fill(0)
    let derrames = 0
    let noAtendida = 0
    for (const k of orden) {
      const b = buscan[k]!
      let mejor = -1
      let mejorPeso = 0
      for (let j = 0; j < n; j++) {
        let w: number
        if (b.tipo === ORIGEN_INTERNO) w = j === b.origen ? 0 : p.destinos[b.origen]![j]!
        else if (b.tipo === ORIGEN_REGION) w = p.tasas.llegan_regiones[j]! * P[j]!
        else w = o.modoExtranjero === 'redes' ? (stock[j]! + 1) ** phi : p.tasas.llegan_extranjero[j]! * P[j]!
        if (w > mejorPeso) {
          mejorPeso = w
          mejor = j
        }
        pesos[j] = capacidad[j]! - ocupadas[j]! >= tamano ? w : 0
      }
      if (mejor >= 0 && pesos[mejor] === 0) derrames++
      const j = rng.categorica(pesos)
      if (j < 0) {
        noAtendida++
        if (b.tipo === ORIGEN_INTERNO) quedan.push(b.origen)
        continue
      }
      quedan.push(j)
      ocupadas[j]! += tamano
      if (b.tipo === ORIGEN_INTERNO) {
        ocupadas[b.origen]! -= tamano
        flujo.set(b.origen * n + j, (flujo.get(b.origen * n + j) ?? 0) + tamano)
      }
      else if (b.tipo === ORIGEN_REGION) llegReg[j]! += tamano
      else {
        llegExt[j]! += tamano
        stock[j]! += tamano
      }
    }

    // 6. Record the year.
    agentes = quedan
    const pob = personas(contar(agentes))
    r.poblacion.push(pob)
    r.capacidad.push(capacidad.slice())
    r.ocupacion.push(ocupacionDe(pob, capacidad))
    r.flujos.push([...flujo].map(([clave, v]) => ({ origen: Math.floor(clave / n), destino: clave % n, personas: v })))
    r.nacimientos.push(nacimientos)
    r.defunciones.push(defunciones)
    r.llegadasRegiones.push(llegReg)
    r.llegadasExtranjero.push(llegExt)
    r.salidasRegion.push(salidas)
    r.saturadas.push(limitada ? pob.map((v, j) => (capacidad[j]! - v < tamano ? j : -1)).filter((j) => j >= 0) : [])
    r.derrames.push(derrames)
    r.noAtendida.push(noAtendida)
  }
  return r
}

function cuantil(ordenados: number[], q: number): number {
  const x = (ordenados.length - 1) * q
  const a = Math.floor(x)
  const b = Math.min(a + 1, ordenados.length - 1)
  return ordenados[a]! + (ordenados[b]! - ordenados[a]!) * (x - a)
}

/** p10, p50 and p90 over `n` runs (seeds semilla, semilla + 1, …), per year and comuna and for the region. */
export function simularReplicas(p: ParametrosAbm, o: OpcionesAbm, replicas: number) {
  const corridas = Array.from({ length: replicas }, (_, k) => simular(p, { ...o, semilla: o.semilla + k }))
  const anios = p.anios.length
  const n = p.comunas.length
  const banda = (valores: (t: number, c: ResultadoAbm) => number) => {
    const out = { p10: [] as number[], p50: [] as number[], p90: [] as number[] }
    for (let t = 0; t < anios; t++) {
      const xs = corridas.map((c) => valores(t, c)).sort((a, b) => a - b)
      out.p10.push(cuantil(xs, 0.1))
      out.p50.push(cuantil(xs, 0.5))
      out.p90.push(cuantil(xs, 0.9))
    }
    return out
  }
  const porComuna = Array.from({ length: n }, (_, i) => banda((t, c) => c.poblacion[t]![i]!))
  const matriz = (k: 'p10' | 'p50' | 'p90') => Array.from({ length: anios }, (_, t) => porComuna.map((b) => b[k][t]!))
  return {
    p10: matriz('p10'),
    p50: matriz('p50'),
    p90: matriz('p90'),
    total: banda((t, c) => c.poblacion[t]!.reduce((s, v) => s + v, 0)),
    corridas,
  }
}
