import { describe, expect, it } from 'vitest'
import { aPrioridad, calcularRiesgo, nivelRiesgo, riesgoPorPosicion, textoPosicion, veredictoGeneral, veredictoVariable } from './riesgo'
import type { Variable } from './types'

const aire: Variable = { id: 'aire', nombre: 'Aire', unidad: 'µg/m³', mejor: 'menor' }
const crece: Variable = { id: 'crece', nombre: 'Crecimiento', unidad: '%', mejor: 'mayor' }

const filas = [
  { codigo: 'a', valores: { aire: 10, crece: 5 } },
  { codigo: 'b', valores: { aire: 20, crece: 0 } },
  { codigo: 'c', valores: { aire: 30, crece: -5 } },
]

describe('riesgoPorPosicion', () => {
  it('la mejor comuna tiene 0 y la peor 100, sin importar qué tan lejos esté', () => {
    const r = riesgoPorPosicion(new Map([['a', 1], ['b', 2], ['c', 1000]]), 'menor')
    expect([r.get('a'), r.get('b'), r.get('c')]).toEqual([0, 50, 100])
  })
  it('se invierte cuando mayor es mejor y los empates comparten riesgo', () => {
    const r = riesgoPorPosicion(new Map([['a', 5], ['b', 5], ['c', 1]]), 'mayor')
    expect([r.get('a'), r.get('b'), r.get('c')]).toEqual([0, 0, 100])
  })
})

describe('calcularRiesgo', () => {
  it('ordena de menor a mayor riesgo y numera los puestos', () => {
    const r = calcularRiesgo(filas, [aire, crece], { aire: 5, crece: 5 })
    expect(r.filas.map((f) => f.codigo)).toEqual(['a', 'b', 'c'])
    expect(r.filas.map((f) => f.indice)).toEqual([0, 50, 100])
    expect(r.porCodigo.get('c')!.puesto).toBe(3)
    expect(r.total).toBe(3)
  })
  it('pondera por prioridad y deja las partes aunque la prioridad sea cero', () => {
    const mixto = [
      { codigo: 'a', valores: { aire: 10, crece: -5 } },
      { codigo: 'b', valores: { aire: 30, crece: 5 } },
    ]
    const r = calcularRiesgo(mixto, [aire, crece], { aire: 9, crece: 1 })
    expect(r.porCodigo.get('a')!.indice).toBeCloseTo(10)
    expect(r.porCodigo.get('b')!.indice).toBeCloseTo(90)
    const solo = calcularRiesgo(mixto, [aire, crece], { aire: 10, crece: 0 })
    expect(solo.usadas).toEqual(['aire'])
    expect(solo.porCodigo.get('a')!.partes.crece).toBe(100)
  })
  it('una comuna sin dato no tiene índice ni puesto y va al final', () => {
    const r = calcularRiesgo([...filas, { codigo: 'z', valores: {} }], [aire], { aire: 1 })
    expect(r.filas.at(-1)).toMatchObject({ codigo: 'z', indice: null, puesto: null })
    expect(r.total).toBe(3)
  })
})

describe('textos y veredictos', () => {
  it('parte la escala en tercios', () => {
    expect([nivelRiesgo(33), nivelRiesgo(34), nivelRiesgo(66), nivelRiesgo(67)]).toEqual(['bajo', 'medio', 'medio', 'alto'])
  })
  it('dice la posición en palabras', () => {
    expect(textoPosicion(85)).toBe('peor que el 85 % de las comunas')
    expect(textoPosicion(30)).toBe('mejor que el 70 % de las comunas')
    expect(textoPosicion(100)).toBe('la peor de la región')
  })
  it('convierte los pesos del archivo en prioridades de 0 a 10', () => {
    expect([aPrioridad(0.6), aPrioridad(0.34), aPrioridad(0)]).toEqual([6, 3, 0])
  })
  it('el veredicto general dice puesto y hacia dónde va', () => {
    const v = veredictoGeneral({ codigo: 'x', indice: 60, partes: {}, puesto: 30 }, 52, { indice: 72, anio: 2036 })!
    expect(v.titulo).toBe('Riesgo medio')
    expect(v.razon).toBe('puesto 30 de 52')
    expect(v.futuro).toBe('En 2036 sube a 72 y pasa a riesgo alto')
    expect(veredictoGeneral({ codigo: 'x', indice: null, partes: {}, puesto: null }, 52)).toBeNull()
  })
  it('el veredicto de una variable sigue su sentido', () => {
    const v = veredictoVariable(90, [-2, -10, -20], [2026, 2027, 2028], 0, crece)
    expect(v.titulo).toBe('Riesgo alto')
    expect(v.futuro).toBe('Empeora: −20,0 % en 2028')
    expect(veredictoVariable(10, [2000, 2005], [2026, 2027], 0, { mejor: 'menor', unidad: 'casos' }).futuro).toBe('No cambia: 2.005 en 2027')
  })
})
