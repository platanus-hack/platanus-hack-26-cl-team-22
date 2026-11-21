import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { MULTIPLICADORES_BASE, cambiosPorComuna, leerDemografia, mayoresFlujos, proyectarDemografia } from './demografia'

const ruta = fileURLToPath(new URL('../../public/datos/demografia.json', import.meta.url))
const datos = leerDemografia(JSON.parse(readFileSync(ruta, 'utf-8')))

function maxErrorRelativo(a: number[][], b: number[][]): number {
  let max = 0
  a.forEach((fila, t) => fila.forEach((v, i) => {
    max = Math.max(max, Math.abs(v - b[t]![i]!) / Math.max(1, Math.abs(b[t]![i]!)))
  }))
  return max
}

describe('proyectarDemografia: parity with Python (experiments/validar_poblacion.proyectar)', () => {
  it('reproduces the default open-model projection', () => {
    const r = proyectarDemografia(datos, MULTIPLICADORES_BASE)
    expect(maxErrorRelativo(r.poblacion, datos.referencia.por_defecto)).toBeLessThan(1e-9)
  })

  it('reproduces the closed model when every external rate is switched off', () => {
    const cero = { natalidad: 0, mortalidad: 0, llegan_regiones: 0, llegan_extranjero: 0, salen_regiones: 0 }
    const r = proyectarDemografia(datos, cero)
    expect(maxErrorRelativo(r.poblacion, datos.referencia.cerrado)).toBeLessThan(1e-9)
  })
})

describe('proyectarDemografia: behaviour', () => {
  it('has one row per year starting at the census population', () => {
    const r = proyectarDemografia(datos, MULTIPLICADORES_BASE)
    expect(r.poblacion).toHaveLength(datos.anios.length)
    expect(r.poblacion[0]).toEqual(datos.poblacion_inicial)
  })

  it('keeps the regional total in the closed model', () => {
    const cero = { natalidad: 0, mortalidad: 0, llegan_regiones: 0, llegan_extranjero: 0, salen_regiones: 0 }
    const r = proyectarDemografia(datos, cero)
    const total = (f: number[]) => f.reduce((s, v) => s + v, 0)
    expect(total(r.poblacion.at(-1)!)).toBeCloseTo(total(r.poblacion[0]!), 3)
  })

  it('grows the region more when arrivals from abroad double', () => {
    const total = (m: typeof MULTIPLICADORES_BASE) =>
      proyectarDemografia(datos, m).poblacion.at(-1)!.reduce((s, v) => s + v, 0)
    expect(total({ ...MULTIPLICADORES_BASE, llegan_extranjero: 2 })).toBeGreaterThan(total(MULTIPLICADORES_BASE))
  })

  it('returns the internal moves of each simulated year', () => {
    const r = proyectarDemografia(datos, MULTIPLICADORES_BASE)
    expect(r.flujos).toHaveLength(datos.anios.length - 1)
    expect(r.flujos[0]).toHaveLength(datos.comunas.length)
  })
})

describe('mayoresFlujos', () => {
  it('lists the largest origin-destination moves first, skipping stayers', () => {
    const top = mayoresFlujos([[0, 5, 1], [9, 0, 2], [3, 7, 0]], ['a', 'b', 'c'], 2)
    expect(top).toEqual([{ origen: 'b', destino: 'a', personas: 9 }, { origen: 'c', destino: 'b', personas: 7 }])
  })
})

describe('leerDemografia', () => {
  it('rejects a file whose destination matrix does not match the comunas', () => {
    const malo = { ...JSON.parse(readFileSync(ruta, 'utf-8')), destinos: [[1]] }
    expect(() => leerDemografia(malo)).toThrow(/destinos/)
  })
})

describe('cambiosPorComuna', () => {
  it('sorts comunas by change from the first year, largest growth first', () => {
    const comunas = [{ codigo: 'a', nombre: 'A' }, { codigo: 'b', nombre: 'B' }, { codigo: 'c', nombre: 'C' }]
    const out = cambiosPorComuna(comunas, [[100, 200, 50], [110, 180, 60]], 1)
    expect(out.map((x) => x.codigo)).toEqual(['c', 'a', 'b'])
    expect(out[0]).toEqual({ codigo: 'c', nombre: 'C', personas: 10, pct: 20 })
  })
})
