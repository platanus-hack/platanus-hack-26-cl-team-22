import { describe, expect, it } from 'vitest'
import { bordesDiferencia, claseDiferencia, diferencia, maxAbsDiferencia, techoRedondo } from './diferencia'
import type { Simulacion } from './types'

const pt = (p50: number) => ({ p10: p50 - 1, p50, p90: p50 + 1 })

describe('diferencia', () => {
  it('es activo menos base, con ambas bandas', () => {
    const d = diferencia(pt(38), pt(40))!
    expect(d.delta).toBe(-2)
    expect(d.activo.p90).toBe(39)
    expect(d.base.p10).toBe(39)
  })
  it('sin alguno de los dos puntos no hay diferencia', () => {
    expect(diferencia(undefined, pt(1))).toBeUndefined()
    expect(diferencia(pt(1), undefined)).toBeUndefined()
  })
})

describe('escala simétrica', () => {
  it('techoRedondo sube a pasos redondos con mínimo 0,5', () => {
    expect(techoRedondo(0)).toBe(0.5)
    expect(techoRedondo(2.1)).toBe(2.5)
    expect(techoRedondo(2.5)).toBe(2.5)
    expect(techoRedondo(7.2)).toBe(8)
    expect(techoRedondo(31)).toBe(35)
  })
  it('bordes van de −max a +max en 5 clases iguales', () => {
    const b = bordesDiferencia(5)
    expect(b).toHaveLength(6)
    expect(b[0]).toBe(-5)
    expect(b[5]).toBe(5)
    expect(b[3]! - b[2]!).toBeCloseTo(b[1]! - b[0]!)
  })
  it('maxAbsDiferencia toma el mayor |delta| de todas las comunas y años', () => {
    const banda = (v: number[]) => ({ p10: v, p50: v, p90: v })
    const d = {
      trayectorias: {
        base: { a: { v: banda([10, 10]) }, b: { v: banda([20, 20]) } },
        sin: { a: { v: banda([11, 10.5]) }, b: { v: banda([20, 17.2]) } },
      },
    } as unknown as Simulacion
    expect(maxAbsDiferencia(d, 'sin', 'base', 'v')).toBe(3)
    expect(maxAbsDiferencia(d, 'nada', 'base', 'v')).toBe(0.5)
  })
})

describe('claseDiferencia', () => {
  it('cero cae en la clase neutra del medio, para cualquier dirección', () => {
    expect(claseDiferencia(0, 5, 'menor')).toBe(2)
    expect(claseDiferencia(0, 5, 'mayor')).toBe(2)
  })
  it('si menor es mejor, bajar es mejora (clase baja) y subir es empeora (clase alta)', () => {
    expect(claseDiferencia(-5, 5, 'menor')).toBe(0)
    expect(claseDiferencia(-2.5, 5, 'menor')).toBe(1)
    expect(claseDiferencia(2.5, 5, 'menor')).toBe(3)
    expect(claseDiferencia(5, 5, 'menor')).toBe(4)
  })
  it('si mayor es mejor se invierte', () => {
    expect(claseDiferencia(5, 5, 'mayor')).toBe(0)
    expect(claseDiferencia(-5, 5, 'mayor')).toBe(4)
  })
  it('es simétrica y acota los valores fuera de escala', () => {
    expect(claseDiferencia(-99, 5, 'menor')).toBe(0)
    expect(claseDiferencia(99, 5, 'menor')).toBe(4)
    for (const x of [0.3, 1.2, 2.9, 4.4]) {
      expect(claseDiferencia(x, 5, 'menor') + claseDiferencia(-x, 5, 'menor')).toBe(4)
    }
  })
})
