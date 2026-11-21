import { describe, expect, it } from 'vitest'
import { rankear } from './scoring'
import type { Variable } from './types'

const vars: Variable[] = [
  { id: 'pm', nombre: 'PM', unidad: 'µg/m³', mejor: 'menor' },
  { id: 'seg', nombre: 'Seguridad', unidad: 'índice', mejor: 'mayor' },
]

describe('rankear', () => {
  const filas = [
    { codigo: 'a', valores: { pm: 20 } },
    { codigo: 'b', valores: { pm: 40 } },
    { codigo: 'c', valores: { pm: 30 } },
  ]
  it('con menor es mejor, la comuna menos contaminada queda primera', () => {
    const r = rankear(filas, vars, { pm: 1 })
    expect(r.filas.map((f) => f.codigo)).toEqual(['a', 'c', 'b'])
    expect(r.filas[0]!.puntaje).toBe(100)
    expect(r.filas[2]!.puntaje).toBe(0)
  })
  it('ignora pesos de variables sin dato y lo informa', () => {
    const r = rankear(filas, vars, { pm: 0.5, seg: 0.5 })
    expect(r.usadas).toEqual(['pm'])
    expect(r.ignoradas).toEqual(['seg'])
    expect(r.filas[0]!.puntaje).toBe(100)
  })
  it('combina variables con mejor mayor', () => {
    const f = [
      { codigo: 'a', valores: { pm: 20, seg: 1 } },
      { codigo: 'b', valores: { pm: 40, seg: 9 } },
    ]
    expect(rankear(f, vars, { pm: 0.9, seg: 0.1 }).filas[0]!.codigo).toBe('a')
    expect(rankear(f, vars, { pm: 0.1, seg: 0.9 }).filas[0]!.codigo).toBe('b')
  })
  it('sin variables usadas todos quedan con puntaje nulo', () => {
    const r = rankear(filas, vars, { seg: 1 })
    expect(r.filas.every((f) => f.puntaje === null)).toBe(true)
  })
  it('valores iguales no producen NaN', () => {
    const r = rankear([{ codigo: 'a', valores: { pm: 5 } }, { codigo: 'b', valores: { pm: 5 } }], vars, { pm: 1 })
    expect(r.filas[0]!.puntaje).toBe(50)
  })
  it('una comuna sin el valor no recibe puntaje de esa variable', () => {
    const r = rankear([...filas, { codigo: 'z', valores: {} }], vars, { pm: 1 })
    expect(r.filas[r.filas.length - 1]).toEqual({ codigo: 'z', puntaje: null })
  })
})
