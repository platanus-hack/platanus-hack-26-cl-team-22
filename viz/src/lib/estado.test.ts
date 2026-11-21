import { describe, expect, it } from 'vitest'
import { estadoAire, veredictoComuna } from './estado'

const anios = [2026, 2027, 2028, 2029]

describe('estadoAire', () => {
  it('sigue las categorías de la norma: saturada, latente y bajo el 80 %', () => {
    expect(estadoAire(20.1, 20)).toBe('riesgo')
    expect(estadoAire(20, 20)).toBe('limite')
    expect(estadoAire(16, 20)).toBe('limite')
    expect(estadoAire(15.9, 20)).toBe('cumple')
  })
})

describe('veredictoComuna', () => {
  it('dice que mejora pero sigue en riesgo', () => {
    const v = veredictoComuna([25.5, 25, 24.5, 23.8], anios, 0, 20)!
    expect(v.titulo).toBe('En riesgo')
    expect(v.razon).toBe('5,5 sobre la norma de 20')
    expect(v.futuro).toBe('Mejora, pero en 2029 sigue en riesgo')
  })
  it('nombra el año en que sale del riesgo o entra en él', () => {
    expect(veredictoComuna([21, 20.5, 19.8, 19], anios, 0, 20)!.futuro).toBe('Sale del riesgo en 2028')
    expect(veredictoComuna([19, 19.5, 20.4, 21], anios, 0, 20)!.futuro).toBe('Entra en riesgo en 2028')
  })
  it('cuenta desde el año elegido, no desde el primero', () => {
    expect(veredictoComuna([21, 20.5, 19.8, 19], anios, 2, 20)!.titulo).toBe('Al límite')
    expect(veredictoComuna([21, 20.5, 19.8, 19], anios, 3, 20)!.futuro).toBeNull()
  })
  it('avisa cuando la banda cruza la norma', () => {
    expect(veredictoComuna([19.5, 19.5], [2026, 2027], 0, 20, { p10: 18, p90: 21 })!.razon).toContain('la banda la supera')
    expect(veredictoComuna([20.5, 20.5], [2026, 2027], 0, 20, { p10: 19.8, p90: 21 })!.razon).toContain('la banda llega a cumplirla')
  })
  it('una comuna limpia sigue cumpliendo', () => {
    const v = veredictoComuna([7.5, 7.4, 7.4, 7.3], anios, 0, 20)!
    expect(v.titulo).toBe('Cumple la norma')
    expect(v.futuro).toBe('No cambia: en 2029 sigue cumpliendo')
  })
  it('sin norma o sin dato no opina', () => {
    expect(veredictoComuna([25], [2026], 0, 0)).toBeNull()
    expect(veredictoComuna([], [], 0, 20)).toBeNull()
  })
})
