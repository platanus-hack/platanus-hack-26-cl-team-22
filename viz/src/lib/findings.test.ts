import { describe, expect, it } from 'vitest'
import { calcularHallazgos } from './findings'
import type { Politica, Variable } from './types'

const variable: Variable = { id: 'pm', nombre: 'PM', unidad: 'µg/m³', mejor: 'menor' }
const politicas = [{ id: 'p1', nombre: 'Leña' }] as Politica[]
const serie = { p10: [38, 30], p50: [40, 35], p90: [42, 40] }

describe('calcularHallazgos', () => {
  it('describe el cambio entre primer y último año con banda', () => {
    const h = calcularHallazgos({ variable, anios: [2026, 2036], serie, escenarioNombre: 'Base', esBase: true, politicas })
    expect(h).toHaveLength(1)
    expect(h[0]).toContain('Entre 2026 y 2036')
    expect(h[0]).toContain('baja 5,0')
    expect(h[0]).toContain('(mejora)')
    expect(h[0]).toContain('35,0 (30,0–40,0)')
  })
  it('compara con la base y avisa si las bandas se solapan', () => {
    const base = { nombre: 'Todos', serie: { p10: [38, 33], p50: [40, 38], p90: [42, 43] } }
    const h = calcularHallazgos({ variable, anios: [2026, 2036], serie, escenarioNombre: 'X', esBase: false, base, politicas })
    expect(h[1]).toContain('más baja')
    expect(h[1]).toContain('se solapan')
  })
  it('elige la política de mayor efecto absoluto y no inventa si no hay aportes', () => {
    const h = calcularHallazgos({
      variable,
      anios: [2026, 2036],
      serie,
      escenarioNombre: 'Base',
      esBase: true,
      politicas,
      aportes: [
        { politica_id: 'p2', delta_p50_final: 1 },
        { politica_id: 'p1', delta_p50_final: -3.7 },
      ],
    })
    expect(h[1]).toContain('"Leña"')
    expect(h[1]).toContain('baja 3,7')
    expect(calcularHallazgos({ variable, anios: [2026, 2036], serie, escenarioNombre: 'B', esBase: true, politicas })).toHaveLength(1)
  })
  it('detecta cambio casi nulo', () => {
    const plana = { p10: [39, 39], p50: [40, 40.1], p90: [41, 41] }
    const h = calcularHallazgos({ variable, anios: [2026, 2036], serie: plana, escenarioNombre: 'B', esBase: true, politicas })
    expect(h[0]).toContain('casi no cambia')
  })
})
