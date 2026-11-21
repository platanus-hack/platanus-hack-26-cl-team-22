import { describe, expect, it, vi } from 'vitest'
import { limpiarGuia, pedirGuia, urlGuia } from './guia'
import { explicar, gradoDe, PERFILES, prioridadesDe } from './onboarding'
import { calcularRiesgo } from './riesgo'
import type { Variable } from './types'

const vars: Variable[] = [
  { id: 'pm25_anual', nombre: 'Aire', unidad: 'µg/m³', mejor: 'menor' },
  { id: 'crecimiento_poblacion', nombre: 'Crecimiento', unidad: '%', mejor: 'mayor' },
]
const filas = [
  { codigo: 'a', valores: { pm25_anual: 10, crecimiento_poblacion: 9 } },
  { codigo: 'b', valores: { pm25_anual: 20, crecimiento_poblacion: 5 } },
  { codigo: 'c', valores: { pm25_anual: 30, crecimiento_poblacion: 1 } },
]
const nombre = (c: string) => ({ a: 'Lampa', b: 'Buin', c: 'Renca' })[c] ?? c

describe('perfiles y grados', () => {
  it('lleva cualquier prioridad al grado más cercano', () => {
    expect([gradoDe(0), gradoDe(2), gradoDe(6), gradoDe(9), gradoDe(10)]).toEqual([0, 3, 5, 8, 10])
  })
  it('solo da prioridades para variables que existen; las desconocidas parten en medio', () => {
    const empresa = PERFILES.find((p) => p.id === 'empresa')!
    expect(prioridadesDe(empresa, ['crecimiento_poblacion', 'otra'])).toEqual({ crecimiento_poblacion: 8, otra: 5 })
  })
})

describe('explicar', () => {
  it('nombra a la primera, en qué destaca según lo que más pesa, y a las que siguen', () => {
    const pesos = { pm25_anual: 3, crecimiento_poblacion: 8 }
    const t = explicar(calcularRiesgo(filas, vars, pesos), vars, pesos, nombre, 'El modelo no mide suelo.')
    expect(t).toBe('Lampa es la de menor riesgo para ti: la mejor de la región en crecimiento. Le siguen Buin y Renca. El modelo no mide suelo.')
  })
  it('sin datos lo dice', () => {
    expect(explicar(calcularRiesgo([], vars, {}), vars, {}, nombre)).toMatch(/No hay datos/)
  })
})

describe('guía del intermediario', () => {
  it('se queda solo con el texto, sin saltos y acotado', () => {
    expect(limpiarGuia({ texto: '  Hola\n mundo ', otra: { cosa: 1 } })).toEqual({ texto: 'Hola mundo' })
    expect(limpiarGuia({ texto: 'x'.repeat(5000) })!.texto).toHaveLength(600)
  })
  it('rechaza lo que no calza', () => {
    expect(limpiarGuia({ texto: 5 })).toBeNull()
    expect(limpiarGuia({ texto: '   ' })).toBeNull()
    expect(limpiarGuia('hola')).toBeNull()
  })
  it('solo acepta un intermediario por https, o local por http', () => {
    expect(urlGuia('https://x.onrender.com/guia')).toBe('https://x.onrender.com/guia')
    expect(urlGuia('http://localhost:8787/guia')).toBe('http://localhost:8787/guia')
    expect(urlGuia('http://x.com/guia')).toBeNull()
    expect(urlGuia('javascript:alert(1)')).toBeNull()
    expect(urlGuia(undefined)).toBeNull()
  })
  it('si el intermediario falla, no hay guía y no se cae', async () => {
    const pedido = { perfil: 'empresa', contexto: 'x', prioridades: {}, anio: 2026, top: [] }
    expect(await pedirGuia('https://x/guia', pedido, vi.fn().mockRejectedValue(new Error('red')))).toBeNull()
    expect(await pedirGuia('https://x/guia', pedido, vi.fn().mockResolvedValue({ ok: false }))).toBeNull()
    const ok = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ texto: 'Lampa conviene.' }) })
    expect(await pedirGuia('https://x/guia', pedido, ok)).toEqual({ texto: 'Lampa conviene.' })
  })
})
