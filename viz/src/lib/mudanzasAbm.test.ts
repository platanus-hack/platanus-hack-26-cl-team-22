import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { MULTIPLICADORES_BASE, leerDemografia, proyectarDemografia } from './demografia'
import { CORTES_OCUPACION, bandaOcupacion, estadoOcupacion, frecuenciaSaturacion, serieOcupacion, simular, simularReplicas, type OpcionesAbm, type ParametrosAbm, type ResultadoAbm } from './mudanzasAbm'

const ruta = fileURLToPath(new URL('../../public/datos/demografia.json', import.meta.url))
const datos = leerDemografia(JSON.parse(readFileSync(ruta, 'utf-8')))
const n = datos.comunas.length
const suma = (xs: ArrayLike<number>) => Array.from(xs).reduce((a, v) => a + v, 0)
const base: OpcionesAbm = { semilla: 1, modoExtranjero: 'fijo' }

/** Persons entering and leaving each comuna through internal moves in year step `t`. */
function movimientos(r: ResultadoAbm, t: number) {
  const entran = new Array<number>(n).fill(0)
  const salen = new Array<number>(n).fill(0)
  for (const f of r.flujos[t]!) {
    entran[f.destino]! += f.personas
    salen[f.origen]! += f.personas
  }
  return { entran, salen }
}

describe('simular: parity with the deterministic model (Validación 1)', () => {
  // Infinite capacity, fixed foreign geography, multipliers 1: every component's expected value
  // equals the deterministic one, so the replica mean must reproduce it.
  const tamano = 500
  const replicas = 40
  const corridas = Array.from({ length: replicas }, (_, k) =>
    simular(datos, { semilla: 1000 + k, tamanoGrupo: tamano, modoExtranjero: 'fijo' }),
  )
  const anios = datos.anios.length

  it('reproduces the regional total of referencia.por_defecto within 0.5% every year', () => {
    for (let t = 0; t < anios; t++) {
      const media = suma(corridas.map((c) => suma(c.poblacion[t]!))) / replicas
      const ref = suma(datos.referencia.por_defecto[t]!)
      expect(Math.abs(media / ref - 1)).toBeLessThan(0.005)
    }
  })

  it('reproduces each comuna in 2036 within sampling noise', () => {
    // Agents are groups of 500, so the start population is rounded to multiples of 500 (up to
    // 250 persons per comuna). Comparing against the deterministic projection from that same
    // rounded start removes the granularity bias and leaves only sampling noise. One run's 2036
    // population has a standard deviation of roughly sqrt(events) groups (about 6-10% for a comuna
    // of 100-200k persons), so the mean of 40 runs carries about 1-1.5%. Two checks:
    //   - every comuna: |mean − expected| below 4 standard errors of the replica mean (+1 group);
    //   - comunas of 150k persons or more: relative error below 3%.
    const redondeada = datos.poblacion_inicial.map((p) => Math.round(p / tamano) * tamano)
    const esperada = proyectarDemografia({ ...datos, poblacion_inicial: redondeada }, MULTIPLICADORES_BASE).poblacion
    const t = anios - 1
    for (let i = 0; i < n; i++) {
      const xs = corridas.map((c) => c.poblacion[t]![i]!)
      const media = suma(xs) / replicas
      const sd = Math.sqrt(suma(xs.map((x) => (x - media) ** 2)) / (replicas - 1))
      const error = Math.abs(media - esperada[t]![i]!)
      expect(error).toBeLessThan(4 * (sd / Math.sqrt(replicas)) + tamano)
      if (datos.poblacion_inicial[i]! >= 150_000) expect(error / esperada[t]![i]!).toBeLessThan(0.03)
    }
  })
})

describe('simular: reproducibility (Validación 2)', () => {
  it('gives the same trajectory for the same seed', () => {
    expect(simular(datos, { ...base, semilla: 7 })).toEqual(simular(datos, { ...base, semilla: 7 }))
  })

  it('gives another trajectory for another seed', () => {
    expect(simular(datos, { ...base, semilla: 7 }).poblacion).not.toEqual(simular(datos, { ...base, semilla: 8 }).poblacion)
  })
})

describe('simular: accounting (Validación 3)', () => {
  it.each([
    ['infinite capacity', {}],
    ['finite capacity', { capacidad_inicial: datos.poblacion_inicial.map((p) => p * 1.02) }],
  ])('balances every comuna every year with %s', (_, extra) => {
    const r = simular({ ...datos, ...extra }, { ...base, modoExtranjero: 'redes', semilla: 3 })
    for (let t = 0; t + 1 < datos.anios.length; t++) {
      const { entran, salen } = movimientos(r, t)
      for (let i = 0; i < n; i++) {
        const esperado =
          r.poblacion[t]![i]! +
          r.nacimientos[t]![i]! -
          r.defunciones[t]![i]! +
          entran[i]! +
          r.llegadasRegiones[t]![i]! +
          r.llegadasExtranjero[t]![i]! -
          salen[i]! -
          r.salidasRegion[t]![i]!
        expect(r.poblacion[t + 1]![i]).toBe(esperado)
      }
    }
  })

  it('starts at the census population rounded to whole groups and reports one row per year', () => {
    const r = simular(datos, { ...base, tamanoGrupo: 250 })
    expect(r.poblacion).toHaveLength(datos.anios.length)
    expect(r.flujos).toHaveLength(datos.anios.length - 1)
    expect(r.poblacion[0]).toEqual(datos.poblacion_inicial.map((p) => Math.round(p / 250) * 250))
    expect(r.ocupacion[0]!.every((v) => v === null)).toBe(true)
  })

  it('never moves anyone from a comuna to itself', () => {
    const r = simular(datos, base)
    expect(r.flujos.flat().every((f) => f.origen !== f.destino && f.personas > 0)).toBe(true)
  })
})

describe('simular: capacity (Validación 4)', () => {
  const params: ParametrosAbm = { ...datos, capacidad_inicial: datos.poblacion_inicial.map((p) => p * 1.01) }
  const r = simular(params, { ...base, semilla: 5 })

  it('never leaves a comuna above capacity after it received moves or arrivals', () => {
    for (let t = 0; t + 1 < datos.anios.length; t++) {
      const { entran } = movimientos(r, t)
      for (let j = 0; j < n; j++) {
        const recibio = entran[j]! + r.llegadasRegiones[t]![j]! + r.llegadasExtranjero[t]![j]! > 0
        if (recibio) expect(r.ocupacion[t + 1]![j]!).toBeLessThanOrEqual(1 + 1e-12)
      }
    }
  })

  it('lets births overfill a comuna and records it', () => {
    const sobre = r.ocupacion.flat().some((v) => v !== null && v > 1)
    expect(sobre).toBe(true)
  })

  it('records saturated comunas, spills and unmet demand', () => {
    expect(r.saturadas.some((s) => s.length > 0)).toBe(true)
    expect(suma(r.derrames)).toBeGreaterThan(0)
    expect(suma(r.noAtendida)).toBeGreaterThan(0)
  })

  it('grows capacity each year with building permits', () => {
    const permisos = datos.poblacion_inicial.map(() => 100)
    const ppv = datos.poblacion_inicial.map(() => 3)
    const c = simular({ ...params, permisos_anuales: permisos, personas_por_vivienda: ppv }, base)
    expect(c.capacidad[1]![0]! - c.capacidad[0]![0]!).toBeCloseTo(300, 9)
    expect(c.capacidad.at(-1)![0]! - c.capacidad[0]![0]!).toBeCloseTo(300 * (datos.anios.length - 1), 6)
  })

  it('rejects building permits without persons per dwelling', () => {
    expect(() => simular({ ...params, permisos_anuales: datos.poblacion_inicial.map(() => 1) }, base)).toThrow(/personas_por_vivienda/)
  })
})

describe('simular: network feedback', () => {
  it('sends more of the arrivals from abroad to the comuna with the larger stock when phi > 1', () => {
    const stock = datos.poblacion_inicial.map((_, i) => (i === 0 ? 100_000 : 1_000))
    const parte = (phi: number) => {
      const r = simular({ ...datos, stock_extranjero: stock, phi }, { ...base, modoExtranjero: 'redes' })
      return suma(r.llegadasExtranjero.map((f) => f[0]!)) / suma(r.llegadasExtranjero.map(suma))
    }
    expect(parte(1.5)).toBeGreaterThan(parte(0) + 0.1)
  })
})

describe('simular: user events', () => {
  it('ola_migratoria raises arrivals from abroad only in its years', () => {
    const sin = simular(datos, base)
    const con = simular(datos, { ...base, eventos: [{ tipo: 'ola_migratoria', desde: 2026, anios: 2, m: 3 }] })
    const total = (r: ResultadoAbm, t: number) => suma(r.llegadasExtranjero[t]!)
    // Step t covers anios[t] → anios[t + 1]; 2026 and 2027 are steps 2 and 3.
    expect(total(con, 2)).toBeGreaterThan(2 * total(sin, 2))
    expect(total(con, 3)).toBeGreaterThan(2 * total(sin, 3))
    expect(total(con, 0)).toBe(total(sin, 0))
  })

  it('crisis raises internal moves and arrivals in its years', () => {
    const sin = simular(datos, base)
    const con = simular(datos, { ...base, eventos: [{ tipo: 'crisis', desde: 2025, anios: 1, m: 2 }] })
    const mov = (r: ResultadoAbm) => suma(r.flujos[1]!.map((f) => f.personas))
    expect(mov(con)).toBeGreaterThan(1.5 * mov(sin))
    expect(suma(con.llegadasRegiones[1]!)).toBeGreaterThan(1.5 * suma(sin.llegadasRegiones[1]!))
  })

  it('densificar multiplies the building permits of one comuna from its year on', () => {
    const p: ParametrosAbm = {
      ...datos,
      capacidad_inicial: datos.poblacion_inicial.slice(),
      permisos_anuales: datos.poblacion_inicial.map(() => 100),
      personas_por_vivienda: datos.poblacion_inicial.map(() => 3),
    }
    const sin = simular(p, base)
    const con = simular(p, { ...base, eventos: [{ tipo: 'densificar', comuna: 4, desde: 2030, m: 5 }] })
    const t2030 = datos.anios.indexOf(2030)
    expect(con.capacidad[t2030]![4]).toBe(sin.capacidad[t2030]![4])
    expect(con.capacidad.at(-1)![4]! - sin.capacidad.at(-1)![4]!).toBeCloseTo(4 * 300 * (datos.anios.length - 1 - t2030), 6)
    expect(con.capacidad.at(-1)![5]).toBe(sin.capacidad.at(-1)![5])
  })
})

describe('simularReplicas', () => {
  it('returns ordered p10 ≤ p50 ≤ p90 per year and comuna and for the region', () => {
    const q = simularReplicas(datos, { ...base, tamanoGrupo: 1000 }, 9)
    expect(q.p50).toHaveLength(datos.anios.length)
    for (let t = 0; t < datos.anios.length; t++) {
      for (let i = 0; i < n; i++) {
        expect(q.p10[t]![i]).toBeLessThanOrEqual(q.p50[t]![i]!)
        expect(q.p50[t]![i]).toBeLessThanOrEqual(q.p90[t]![i]!)
      }
      expect(q.total.p10[t]).toBeLessThanOrEqual(q.total.p50[t]!)
      expect(q.total.p50[t]).toBeLessThanOrEqual(q.total.p90[t]!)
    }
    expect(q.total.p90.at(-1)!).toBeGreaterThan(q.total.p10.at(-1)!)
  })
})

describe('simular: performance', () => {
  it('runs 12 years with groups of 250 in well under a second', () => {
    simular(datos, base)
    const t0 = performance.now()
    simular(datos, { ...base, semilla: 2 })
    expect(performance.now() - t0).toBeLessThan(1000)
  })
})

describe('summaries of several runs', () => {
  const params: ParametrosAbm = { ...datos, capacidad_inicial: datos.poblacion_inicial.map((p) => p * 1.01) }
  const corridas = [1, 2, 3, 4, 5].map((s) => simular(params, { ...base, semilla: s }))

  it('gives the occupancy band per comuna in percent, ordered p10 ≤ p50 ≤ p90', () => {
    const banda = bandaOcupacion(corridas, 3)
    expect(banda).toHaveLength(n)
    for (const b of banda) {
      expect(b).not.toBeNull()
      expect(b!.p10).toBeLessThanOrEqual(b!.p50)
      expect(b!.p50).toBeLessThanOrEqual(b!.p90)
    }
    const r = corridas[0]!
    expect(bandaOcupacion([r], 3)[0]!.p50).toBeCloseTo(r.ocupacion[3]![0]! * 100, 9)
  })

  it('has no occupancy band without a capacity limit', () => {
    expect(bandaOcupacion([simular(datos, base)], 1).every((b) => b === null)).toBe(true)
  })

  it('counts in how many runs each comuna saturated up to a year, most frequent first', () => {
    const f = frecuenciaSaturacion(corridas, datos.anios.length - 1)
    expect(f.length).toBeGreaterThan(0)
    for (let k = 1; k < f.length; k++) expect(f[k - 1]!.corridas).toBeGreaterThanOrEqual(f[k]!.corridas)
    expect(f.every((x) => x.corridas >= 1 && x.corridas <= corridas.length)).toBe(true)
  })

  it("gives one comuna's occupancy band for every year", () => {
    const serie = serieOcupacion(corridas, 0)
    expect(serie.p50).toHaveLength(datos.anios.length)
    for (let t = 0; t < datos.anios.length; t++) expect(serie.p50[t]).toBeCloseTo(bandaOcupacion(corridas, t)[0]!.p50, 9)
  })
})

describe('estadoOcupacion', () => {
  it('calls a comuna full when it saturates in at least half of the runs', () => {
    expect(estadoOcupacion(80, 10, 20)).toMatchObject({ estado: 'riesgo', titulo: 'Llena' })
  })
  it('warns when it saturates in some run or is above 97 %', () => {
    expect(estadoOcupacion(80, 1, 20)).toMatchObject({ estado: 'limite', titulo: 'Puede llenarse' })
    expect(estadoOcupacion(97.5, 0, 20)).toMatchObject({ estado: 'limite', titulo: 'Puede llenarse' })
  })
  it('has room otherwise', () => {
    expect(estadoOcupacion(97, 0, 20)).toMatchObject({ estado: 'cumple', titulo: 'Con espacio' })
  })
  it('puts the map cuts where the medians fall, so full and overfull share the top level', () => {
    expect(CORTES_OCUPACION.at(-1)).toBeLessThan(100)
    expect(CORTES_OCUPACION).toContain(97)
  })
})
