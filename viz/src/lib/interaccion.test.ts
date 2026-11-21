import { describe, expect, it } from 'vitest'
import type { Diferencia } from './diferencia'
import { accionDeTecla, pasoDemo, PASOS_POR_VISTA, resumirDiferencias, textoBanda, etiquetaModelo, veredicto, vistasDisponibles } from './interaccion'

describe('teclas', () => {
  it('números para vistas, letras para políticas, flechas y espacio para el tiempo', () => {
    expect(accionDeTecla('1', 4, 3)).toEqual({ tipo: 'vista', indice: 0 })
    expect(accionDeTecla('5', 4, 3)).toBeNull()
    expect(accionDeTecla('5', 5, 3)).toEqual({ tipo: 'vista', indice: 4 })
    expect(accionDeTecla('Q', 4, 3)).toEqual({ tipo: 'politica', indice: 0 })
    expect(accionDeTecla('e', 4, 3)).toEqual({ tipo: 'politica', indice: 2 })
    expect(accionDeTecla('r', 4, 3)).toBeNull()
    expect(accionDeTecla('ArrowLeft', 4, 3)).toEqual({ tipo: 'anio', paso: -1 })
    expect(accionDeTecla(' ', 4, 3)).toEqual({ tipo: 'jugar' })
    expect(accionDeTecla('d', 4, 3)).toEqual({ tipo: 'diferencia' })
    expect(accionDeTecla('x', 4, 3)).toBeNull()
  })
  it('la última vista solo existe con validación', () => {
    expect(vistasDisponibles(false).map((v) => v.id)).toEqual(['riesgo', 'plan', 'lena'])
    expect(vistasDisponibles(true)).toHaveLength(4)
    expect(vistasDisponibles(true, true).map((v) => v.id).at(-1)).toBe('mudanzas')
    expect(vistasDisponibles(false, true).map((v) => v.id)).toEqual(['riesgo', 'plan', 'lena', 'mudanzas'])
  })
})

const dif = (delta: number): Diferencia => ({ delta, activo: { p10: 0, p50: delta, p90: 0 }, base: { p10: 0, p50: 0, p90: 0 } })

describe('resumirDiferencias', () => {
  it('cuenta mejoras, empeoramientos y sin cambio, y encuentra el mayor cambio', () => {
    const m = new Map([
      ['a', dif(-2)],
      ['b', dif(0.1)],
      ['c', dif(3)],
      ['d', dif(-0.5)],
    ])
    const r = resumirDiferencias(m, 'menor', 3)
    expect([r.mejoran, r.empeoran, r.sinCambio]).toEqual([2, 1, 1])
    expect(r.mayor?.codigo).toBe('c')
    expect(resumirDiferencias(new Map(), 'menor', 1).mayor).toBeNull()
  })
})

describe('pasoDemo', () => {
  const vistas = ['riesgo', 'plan', 'lena'] as const
  it('recorre vistas y años en orden', () => {
    expect(pasoDemo(0, vistas, 11, 2)).toEqual({ vista: 0, anio: 0, alternar: null })
    expect(pasoDemo(PASOS_POR_VISTA, vistas, 11, 2).vista).toBe(1)
    expect(pasoDemo(3 * PASOS_POR_VISTA, vistas, 11, 2).vista).toBe(0)
    expect(pasoDemo(12, vistas, 11, null).anio).toBe(1)
  })
  it('en el plan despega y vuelve a pegar la misma política (número par de cambios)', () => {
    const cambios = Array.from({ length: PASOS_POR_VISTA }, (_, i) => pasoDemo(PASOS_POR_VISTA + i, vistas, 11, 2).alternar).filter(
      (x) => x !== null,
    )
    expect(cambios).toEqual([2, 2])
    expect(pasoDemo(PASOS_POR_VISTA + 1, vistas, 11, null).alternar).toBeNull()
  })
})

describe('veredicto', () => {
  it('empata dentro de la tolerancia, gana o pierde fuera', () => {
    expect(veredicto(0.9, 0.91)).toBe('empata')
    expect(veredicto(0.9, 3.32)).toBe('gana')
    expect(veredicto(4.29, 1.91)).toBe('pierde')
  })
})

describe('rótulos', () => {
  const f = (n: number) => String(n)
  it('etiquetaModelo corta en los dos puntos y nunca muestra rutas', () => {
    expect(etiquetaModelo('Aire v0: núcleo exponencial isotrópico (docs/modelo-aire.md)', 500, f)).toBe('Modelo de aire v0 · 500 réplicas')
    expect(etiquetaModelo('docs/x.md', undefined, f)).toBe('')
    expect(etiquetaModelo('Modelo urbano', 0, f)).toBe('Modelo urbano')
    expect(etiquetaModelo(undefined, 10, f)).toBe('10 réplicas')
  })
  it('textoBanda dice en palabras cuando la banda no tiene ancho', () => {
    expect(textoBanda(6.57, 6.57, (n) => n.toFixed(2), 'millones')).toBe('sin variación entre réplicas')
    expect(textoBanda(0, 6.29, (n) => n.toFixed(2), 'millones')).toBe('0.00–6.29 millones')
  })
})
