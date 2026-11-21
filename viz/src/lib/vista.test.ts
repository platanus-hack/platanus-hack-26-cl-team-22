import { describe, expect, it } from 'vitest'
import type { GeoFeature } from './geo'
import { ajustarLimites, esGranSantiago, limitesDe, limitesDeCoordenadas, limitesDeVista } from './vista'

const feat = (codigo: string, provincia: string | undefined, coords: unknown, tipo: 'Polygon' | 'MultiPolygon' = 'Polygon'): GeoFeature => ({
  type: 'Feature',
  properties: { codigo, nombre: codigo, provincia },
  geometry: { type: tipo, coordinates: coords },
})

const cuadro = (x: number, y: number) => [[[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1], [x, y]]]

describe('limites', () => {
  it('recorre Polygon y MultiPolygon', () => {
    expect(limitesDeCoordenadas(cuadro(-71, -34))).toEqual([-71, -34, -70, -33])
    expect(limitesDeCoordenadas([cuadro(-71, -34), cuadro(-69, -32)])).toEqual([-71, -34, -68, -31])
  })
  it('ignora coordenadas no numéricas y devuelve null si no hay nada', () => {
    expect(limitesDe([feat('a', undefined, [[['x', 'y']]])])).toBeNull()
    expect(limitesDe([])).toBeNull()
  })
})

describe('Gran Santiago', () => {
  it('incluye la provincia de Santiago, Puente Alto y San Bernardo', () => {
    expect(esGranSantiago({ codigo: '13101', provincia: 'Santiago' })).toBe(true)
    expect(esGranSantiago({ codigo: '13201', provincia: 'Cordillera' })).toBe(true)
    expect(esGranSantiago({ codigo: '13401', provincia: 'Maipo' })).toBe(true)
    expect(esGranSantiago({ codigo: '13301', provincia: 'Chacabuco' })).toBe(false)
    expect(esGranSantiago({ codigo: '13601' })).toBe(false)
  })
  it('sus límites salen de los polígonos y son menores que los de la región', () => {
    const fs = [
      feat('13101', 'Santiago', cuadro(-70.7, -33.5)),
      feat('13201', 'Cordillera', cuadro(-70.6, -33.7)),
      feat('13301', 'Chacabuco', cuadro(-70.8, -33.0)),
      feat('13501', 'Melipilla', cuadro(-71.5, -33.8)),
    ]
    const l = limitesDeVista(fs)!
    expect(l.granSantiago).toEqual([-70.7, -33.7, -69.6, -32.5])
    expect(l.region).toEqual([-71.5, -33.8, -69.6, -32])
    expect(l.granSantiago[2] - l.granSantiago[0]).toBeLessThan(l.region[2] - l.region[0])
  })
  it('si no hay comunas del Gran Santiago, cae a la región', () => {
    const l = limitesDeVista([feat('13301', 'Chacabuco', cuadro(-70.8, -33))])!
    expect(l.granSantiago).toEqual(l.region)
  })
})

describe('ajustarLimites', () => {
  const lim: [number, number, number, number] = [-70.9, -33.7, -70.4, -33.3]
  const sinRelleno = { izq: 0, der: 0, sup: 0, inf: 0 }

  it('centra los límites si no hay relleno', () => {
    const v = ajustarLimites(lim, 1000, 800, sinRelleno)
    expect(v.longitude).toBeCloseTo(-70.65, 4)
    expect(v.latitude).toBeCloseTo(-33.5, 1)
  })
  it('con paneles que tapan, hace zoom menor y corre el centro hacia el lado tapado', () => {
    const libre = ajustarLimites(lim, 1000, 800, sinRelleno)
    const tapado = ajustarLimites(lim, 1000, 800, { izq: 300, der: 100, sup: 0, inf: 0 })
    expect(tapado.zoom).toBeLessThan(libre.zoom)
    // el panel izquierdo es mayor: el centro de la vista queda al oeste del centro de los límites
    expect(tapado.longitude).toBeLessThan(libre.longitude)
  })
  it('un área mayor da más zoom y respeta los topes', () => {
    const chico = ajustarLimites(lim, 600, 400, sinRelleno)
    const grande = ajustarLimites(lim, 1200, 800, sinRelleno)
    expect(grande.zoom).toBeCloseTo(chico.zoom + 1, 5)
    expect(ajustarLimites(lim, 1200, 800, sinRelleno, { maxZoom: 5 }).zoom).toBe(5)
  })
  it('los límites caben en el área libre', () => {
    const rel = { izq: 300, der: 340, sup: 76, inf: 84 }
    const v = ajustarLimites(lim, 1440, 900, rel)
    const px = 512 * 2 ** v.zoom
    const anchoPx = ((lim[2] - lim[0]) / 360) * px
    expect(anchoPx).toBeLessThanOrEqual(1440 - 300 - 340 + 1e-6)
  })
})
