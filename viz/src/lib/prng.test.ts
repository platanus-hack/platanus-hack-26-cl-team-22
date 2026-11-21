import { describe, expect, it } from 'vitest'
import { crearPrng } from './prng'

const media = (xs: number[]) => xs.reduce((a, v) => a + v, 0) / xs.length

describe('crearPrng', () => {
  it('gives the same sequence for the same seed', () => {
    const a = crearPrng(42)
    const b = crearPrng(42)
    const sa = Array.from({ length: 100 }, () => a.uniform())
    const sb = Array.from({ length: 100 }, () => b.uniform())
    expect(sa).toEqual(sb)
  })

  it('gives a different sequence for a different seed', () => {
    const a = crearPrng(1)
    const b = crearPrng(2)
    const sa = Array.from({ length: 20 }, () => a.uniform())
    const sb = Array.from({ length: 20 }, () => b.uniform())
    expect(sa).not.toEqual(sb)
  })

  it('draws uniforms in [0, 1) with mean near 1/2', () => {
    const r = crearPrng(7)
    const xs = Array.from({ length: 50_000 }, () => r.uniform())
    expect(Math.min(...xs)).toBeGreaterThanOrEqual(0)
    expect(Math.max(...xs)).toBeLessThan(1)
    expect(Math.abs(media(xs) - 0.5)).toBeLessThan(0.01)
  })

  it.each([0.3, 4, 25, 80, 300, 5000])('draws Poisson(%f) with mean and variance near lambda', (lambda) => {
    const r = crearPrng(11)
    const n = 40_000
    const xs = Array.from({ length: n }, () => r.poisson(lambda))
    const m = media(xs)
    const v = media(xs.map((x) => (x - m) ** 2))
    // Standard error of the mean is sqrt(lambda / n); allow 4 of them.
    expect(Math.abs(m - lambda)).toBeLessThan(4 * Math.sqrt(lambda / n))
    expect(Math.abs(v / lambda - 1)).toBeLessThan(0.05)
    expect(xs.every((x) => Number.isInteger(x) && x >= 0)).toBe(true)
  })

  it('returns 0 for Poisson(0)', () => {
    expect(crearPrng(3).poisson(0)).toBe(0)
  })

  it('shuffles in place keeping every element', () => {
    const r = crearPrng(5)
    const xs = Int32Array.from({ length: 100 }, (_, i) => i)
    r.barajar(xs)
    expect(Array.from(xs).sort((a, b) => a - b)).toEqual(Array.from({ length: 100 }, (_, i) => i))
    expect(Array.from(xs)).not.toEqual(Array.from({ length: 100 }, (_, i) => i))
  })

  it('samples categories in proportion to their weights and never a zero weight', () => {
    const r = crearPrng(9)
    const pesos = [1, 0, 3]
    const cuenta = [0, 0, 0]
    for (let k = 0; k < 40_000; k++) cuenta[r.categorica(pesos)]!++
    expect(cuenta[1]).toBe(0)
    expect(cuenta[2]! / cuenta[0]!).toBeGreaterThan(2.8)
    expect(cuenta[2]! / cuenta[0]!).toBeLessThan(3.2)
  })

  it('returns -1 when every weight is zero', () => {
    expect(crearPrng(9).categorica([0, 0])).toBe(-1)
  })
})
