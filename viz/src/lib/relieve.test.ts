import { describe, expect, it } from 'vitest'
import { claseFondo, variableDeClase, type DatosFondo } from './fondo'
import { aRgb, CAPAS, curva, elegirMapa, esEstiloValido, estiloRelieve, MARCA_BASE, mezclar, resolverBase, siguienteMapa } from './relieve'

const base = {
  version: 8,
  sources: { ne2_shaded: { type: 'raster' }, openmaptiles: { type: 'vector', url: 'https://ejemplo/planet' } },
  glyphs: 'x',
  layers: [
    { id: 'fondo', type: 'background' },
    { id: 'sombra-ne', type: 'raster', source: 'ne2_shaded' },
    { id: 'calles', type: 'line', source: 'openmaptiles', 'source-layer': 'transportation' },
    { id: 'nombre-calle', type: 'symbol', source: 'openmaptiles', 'source-layer': 'transportation_name' },
    { id: 'ciudad', type: 'symbol', source: 'openmaptiles', 'source-layer': 'place' },
  ],
}
const colores = { tinta: '#111111', papel: '#fafaf7', disco: '#ee7b22', corte: '#d9d9d0', edificio: '#e9e7df', agua: '#1f6fb2', aguaClara: '#d7ecfa' }

describe('elegirMapa', () => {
  const ok = async () => base
  const no = async () => null
  it('prefiere el mapa en línea', async () => {
    expect((await elegirMapa(null, { linea: ok, local: ok })).tipo).toBe('linea')
  })
  it('sin red cae al paquete local y, sin paquete, al plano', async () => {
    expect((await elegirMapa(null, { linea: no, local: ok })).tipo).toBe('local')
    expect((await elegirMapa(null, { linea: no, local: no })).tipo).toBe('plano')
  })
  it('respeta el respaldo pedido sin tocar la red', async () => {
    let red = 0
    const linea = async () => {
      red++
      return base
    }
    expect((await elegirMapa('local', { linea, local: ok })).tipo).toBe('local')
    expect((await elegirMapa('plano', { linea, local: ok })).tipo).toBe('plano')
    expect(red).toBe(0)
  })
  it('la tecla de emergencia recorre los tres mapas', () => {
    expect(siguienteMapa('linea')).toBe('local')
    expect(siguienteMapa('local')).toBe('plano')
    expect(siguienteMapa('plano')).toBe('linea')
  })
})

describe('estilo', () => {
  it('rechaza lo que no es un estilo (por ejemplo, index.html servido como respaldo)', () => {
    expect(esEstiloValido('<!doctype html>')).toBe(false)
    expect(esEstiloValido({ sources: {}, layers: [] })).toBe(false)
    expect(esEstiloValido(base)).toBe(true)
    expect(() => estiloRelieve(null, colores)).toThrow()
  })
  it('agrega terreno y capas de datos, y quita los rótulos de lugares', () => {
    const e = estiloRelieve(base, colores)
    const capas = e.layers as { id: string; type: string }[]
    const ids = capas.map((l) => l.id)
    expect(ids).not.toContain('ciudad')
    expect(ids).not.toContain('sombra-ne')
    expect(ids.indexOf(CAPAS.relleno)).toBeLessThan(ids.indexOf('nombre-calle'))
    expect(ids.at(-1)).toBe(CAPAS.nombres)
    expect(e.terrain).toMatchObject({ source: 'relieve-dem' })
    expect(Object.keys(e.sources as object)).toEqual(expect.arrayContaining(['comunas', 'rotulos', 'cintas', 'discos', 'relieve-sombra']))
    expect(base.layers).toHaveLength(5) // no modifica el estilo recibido
  })
  it('usa el relieve del paquete local si el estilo ya lo trae', () => {
    const local = { ...base, sources: { ...base.sources, 'relieve-dem': { type: 'raster-dem', tiles: [`${MARCA_BASE}/relieve/{z}/{x}/{y}.webp`] } } }
    const e = estiloRelieve(resolverBase(local, 'http://localhost:5411/mapas/'), colores)
    const dem = (e.sources as Record<string, { tiles?: string[] }>)['relieve-dem']!
    expect(dem.tiles![0]).toBe('http://localhost:5411/mapas/relieve/{z}/{x}/{y}.webp')
  })
})

describe('color y curvas', () => {
  it('lee colores en hex y rgb', () => {
    expect(aRgb('#fafaf7')).toEqual([250, 250, 247])
    expect(aRgb(' #fff ')).toEqual([255, 255, 255])
    expect(aRgb('rgb(17, 17, 17)')).toEqual([17, 17, 17])
    expect(aRgb('papel')).toBeNull()
  })
  it('mezcla sin salirse de los extremos', () => {
    expect(mezclar([0, 0, 0], [100, 200, 50], 0.5)).toEqual([50, 100, 25])
    expect(mezclar([0, 0, 0], [100, 200, 50], 3)).toEqual([100, 200, 50])
  })
  it('la cinta empieza y termina en sus comunas', () => {
    const c = curva([-70.7, -33.5], [-70.6, -33.4])
    expect(c[0]).toEqual([-70.7, -33.5])
    expect(c.at(-1)![0]).toBeCloseTo(-70.6)
    expect(c.at(-1)![1]).toBeCloseTo(-33.4)
  })
})

describe('claseFondo', () => {
  const d: DatosFondo = {
    modo: 'valor',
    cortes: [10, 15, 20, 23, 26],
    puntos: new Map([['13101', { p10: 24, p50: 25, p90: 25.5 }]]),
    difs: null,
    difMax: 1,
    mejor: 'menor',
    lena: null,
  }
  it('da el papel del nivel y deja sin color lo que no tiene dato', () => {
    expect(claseFondo(d, '13101', '13101')).toBe('nivel-4')
    expect(claseFondo(d, '13999', undefined)).toBe('sin-dato')
    expect(variableDeClase('nivel-4')).toBe('--nivel-4')
    expect(variableDeClase('dif-0')).toBe('--papel')
    expect(variableDeClase('sin-dato')).toBeNull()
  })
})
