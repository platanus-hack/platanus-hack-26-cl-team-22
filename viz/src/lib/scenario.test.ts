import { describe, expect, it } from 'vitest'
import { alternar, buscarEscenario, escenarioInicial, lecturasDisponibles, resolverSeleccion } from './scenario'
import type { Escenario } from './types'

const esc: Escenario[] = [
  { id: 'base', nombre: 'Base', politicas_activas: ['a', 'b', 'c'] },
  { id: 'sin-a', nombre: 'Sin A', politicas_activas: ['b', 'c'] },
]

describe('escenarios', () => {
  it('encuentra el escenario por conjunto exacto, sin importar el orden', () => {
    expect(buscarEscenario(esc, new Set(['c', 'b']))?.id).toBe('sin-a')
    expect(buscarEscenario(esc, new Set(['c', 'b', 'a']))?.id).toBe('base')
  })
  it('devuelve null si la combinación no está calculada', () => {
    expect(buscarEscenario(esc, new Set(['a']))).toBeNull()
    expect(buscarEscenario(esc, new Set())).toBeNull()
  })
  it('conserva el último escenario válido si no hay coincidencia', () => {
    const r = resolverSeleccion(esc, new Set(['a']), esc[1]!)
    expect(r.calculada).toBe(false)
    expect(r.escenario.id).toBe('sin-a')
  })
  it('elige base como inicial, o el de más políticas', () => {
    expect(escenarioInicial(esc).id).toBe('base')
    expect(escenarioInicial([esc[1]!, { id: 'x', nombre: 'X', politicas_activas: ['a', 'b', 'c', 'd'] }]).id).toBe('x')
  })
  it('con lecturas: el mismo conjunto se distingue por la lectura', () => {
    const conLectura: Escenario[] = [
      { id: 'base', nombre: 'Base', politicas_activas: ['a'], lectura: 'conservadora' },
      { id: 'sin-a', nombre: 'Sin A', politicas_activas: [], lectura: 'conservadora' },
      { id: 'base-opt', nombre: 'Base optimista', politicas_activas: ['a'], lectura: 'optimista' },
    ]
    expect(buscarEscenario(conLectura, new Set(['a']), undefined, 'conservadora')?.id).toBe('base')
    expect(buscarEscenario(conLectura, new Set(['a']), 'optimista', 'conservadora')?.id).toBe('base-opt')
    const r = resolverSeleccion(conLectura, new Set(), conLectura[2]!, 'optimista', 'conservadora')
    expect(r).toEqual({ escenario: conLectura[2], calculada: false })
    expect(lecturasDisponibles(conLectura, 'conservadora')).toEqual(['conservadora', 'optimista'])
    expect(lecturasDisponibles(esc)).toEqual([])
  })
  it('alterna sin mutar', () => {
    const s = new Set(['a'])
    expect([...alternar(s, 'b')].sort()).toEqual(['a', 'b'])
    expect([...alternar(s, 'a')]).toEqual([])
    expect([...s]).toEqual(['a'])
  })
})
