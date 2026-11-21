import { describe, expect, it } from 'vitest'
import { anotar, circulo, emparejar, featuresDeRespaldo, leerFeatures } from './geo'
import type { Comuna } from './types'

const comunas = [
  { codigo: '13101', nombre: 'Santiago', lat: 0, lon: 0, base: {} },
  { codigo: 'maipu', nombre: 'Maipú', lat: 0, lon: 0, base: {} },
  { codigo: 'x', nombre: 'Sin polígono', lat: 0, lon: 0, base: {} },
] as Comuna[]

const raw = {
  features: [
    { properties: { codigo: '13101', nombre: 'Santiago' }, geometry: { type: 'Polygon', coordinates: [] } },
    { properties: { codigo: '13119', nombre: 'MAIPU' }, geometry: { type: 'Polygon', coordinates: [] } },
    { properties: { codigo: '13120', nombre: 'Ñuñoa' }, geometry: { type: 'MultiPolygon', coordinates: [] } },
    { properties: { nombre: 5 }, geometry: { type: 'Polygon', coordinates: [] } },
    { properties: { nombre: 'Punto' }, geometry: { type: 'Point', coordinates: [] } },
  ],
}

describe('geo', () => {
  it('descarta features inválidas', () => {
    expect(leerFeatures(raw)).toHaveLength(3)
    expect(leerFeatures(null)).toEqual([])
  })
  it('empareja por código y luego por nombre sin tildes ni mayúsculas', () => {
    const f = leerFeatures(raw)
    const m = emparejar(comunas, f)
    expect(m.get('13101')).toBe(0)
    expect(m.get('maipu')).toBe(1)
    expect(m.has('x')).toBe(false)
    const a = anotar(f, m)
    expect(a[2]!.properties.simCodigo).toBeUndefined()
    expect(a[1]!.properties.simCodigo).toBe('maipu')
  })
  it('dibuja círculos cerrados de respaldo', () => {
    const c = circulo(-70, -33, 3)
    expect(c[0]).toEqual(c[c.length - 1])
    expect(featuresDeRespaldo(comunas)).toHaveLength(3)
  })
})
