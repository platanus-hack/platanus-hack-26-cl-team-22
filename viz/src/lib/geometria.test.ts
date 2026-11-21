import { describe, expect, it } from 'vitest'
import { apilarLabios, apilarNivel, hash01 } from './capas'
import { anilloCircular, diezmar, escalarAnillo, rutaFestoneada, rutaRodela } from './feston'
import {
  ajustarCaja,
  areaAnillo,
  cajaDePoligonos,
  centroideAnillo,
  crearProyeccion,
  dentroPoligono,
  interpolarVista,
  limitarVista,
  proyectarGeometria,
  puntoInterior,
  rutaDeAnillos,
  zoomEn,
  type Poligono,
  type Pt,
} from './proyeccion'

const cuadro = (x: number, y: number, l: number): Pt[] => [
  [x, y],
  [x + l, y],
  [x + l, y + l],
  [x, y + l],
]

describe('proyección', () => {
  it('corrige la longitud por el coseno de la latitud central y pone el norte arriba', () => {
    const p = crearProyeccion([-71, -34, -70, -32])
    const [x, y] = p(-70, -33)
    expect(x).toBeCloseTo(-70 * Math.cos((33 * Math.PI) / 180), 9)
    expect(y).toBe(33)
    expect(p(-70, -32)[1]).toBeLessThan(p(-70, -34)[1])
  })
  it('lee Polygon y MultiPolygon y descarta lo mal formado', () => {
    const id = (lon: number, lat: number): Pt => [lon, lat]
    const sq = [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
    expect(proyectarGeometria({ type: 'Polygon', coordinates: sq }, id)).toHaveLength(1)
    expect(proyectarGeometria({ type: 'MultiPolygon', coordinates: [sq, sq, 'x'] }, id)).toHaveLength(2)
    expect(proyectarGeometria({ type: 'Polygon', coordinates: [[['a', 'b']]] }, id)).toHaveLength(0)
    expect(proyectarGeometria({ type: 'Point', coordinates: [0, 0] }, id)).toHaveLength(0)
  })
  it('escribe rutas cerradas', () => {
    expect(rutaDeAnillos([cuadro(0, 0, 1)])).toBe('M0.00000,0.00000L1.00000,0.00000L1.00000,1.00000L0.00000,1.00000Z')
  })
})

describe('geometría de polígonos', () => {
  it('área con signo, centroide y punto dentro', () => {
    expect(areaAnillo(cuadro(0, 0, 2))).toBe(4)
    expect(areaAnillo([...cuadro(0, 0, 2)].reverse())).toBe(-4)
    expect(centroideAnillo(cuadro(0, 0, 2))).toEqual([1, 1])
    expect(dentroPoligono([1, 1], [cuadro(0, 0, 2)])).toBe(true)
    expect(dentroPoligono([1, 1], [cuadro(0, 0, 2), cuadro(0.5, 0.5, 1)])).toBe(false)
  })
  it('el punto interior cae dentro aunque el centroide no (forma de U)', () => {
    const u: Pt[] = [[0, 0], [3, 0], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3]]
    const pol: Poligono = [u]
    expect(dentroPoligono(centroideAnillo(u), pol)).toBe(false)
    expect(dentroPoligono(puntoInterior(pol), pol)).toBe(true)
  })
})

describe('vista', () => {
  const caja = { x0: 0, y0: 0, x1: 10, y1: 5 }
  it('hace caber y centra la caja en el área libre', () => {
    const v = ajustarCaja(caja, 200, 200, { izq: 0, der: 0, sup: 0, inf: 0 })
    expect(v.k).toBe(20)
    expect(5 * v.k + v.ty).toBe(150)
    expect(0 * v.k + v.ty).toBe(50)
  })
  it('interpola: en 0 y 1 devuelve los extremos', () => {
    const a = ajustarCaja(caja, 400, 300, { izq: 10, der: 10, sup: 10, inf: 10 })
    const b = ajustarCaja({ x0: 2, y0: 2, x1: 3, y1: 3 }, 400, 300, { izq: 10, der: 10, sup: 10, inf: 10 })
    const i0 = interpolarVista(a, b, 0, 400, 300)
    const i1 = interpolarVista(a, b, 1, 400, 300)
    expect(i0.k).toBeCloseTo(a.k, 9)
    expect(i0.tx).toBeCloseTo(a.tx, 9)
    expect(i1.k).toBeCloseTo(b.k, 9)
    expect(i1.ty).toBeCloseTo(b.ty, 9)
    expect(interpolarVista(a, b, 0.5, 400, 300).k).toBeCloseTo(Math.sqrt(a.k * b.k), 9)
  })
  it('el zoom deja fijo el punto bajo el puntero', () => {
    const v = zoomEn({ k: 2, tx: 10, ty: 20 }, 3, 50, 60)
    const mundoAntes = [(50 - 10) / 2, (60 - 20) / 2]
    expect(mundoAntes[0]! * v.k + v.tx).toBeCloseTo(50, 9)
    expect(mundoAntes[1]! * v.k + v.ty).toBeCloseTo(60, 9)
  })
  it('limita el zoom y no deja escapar la región', () => {
    const v = limitarVista({ k: 100, tx: -5000, ty: 0 }, caja, 400, 300, 1, 50, 80)
    expect(v.k).toBe(50)
    expect(caja.x1 * v.k + v.tx).toBeGreaterThanOrEqual(80 - 1e-9)
  })
  it('caja de polígonos', () => {
    expect(cajaDePoligonos([[cuadro(1, 2, 3)]])).toEqual({ x0: 1, y0: 2, x1: 4, y1: 5 })
    expect(cajaDePoligonos([])).toBeNull()
  })
})

describe('festón', () => {
  it('reparte cada tramo en arcos hacia afuera según el sentido del anillo', () => {
    const d = rutaFestoneada(cuadro(0, 0, 10), 5)
    expect(d.match(/A/g)).toHaveLength(8)
    expect(d).toContain(' 0 0 1 ')
    const inv = rutaFestoneada([...cuadro(0, 0, 10)].reverse(), 5)
    expect(inv).toContain(' 0 0 0 ')
  })
  it('diezma vértices muy juntos y escala sobre un centro', () => {
    const r: Pt[] = [[0, 0], [0.1, 0], [5, 0], [5, 5], [0, 5], [0, 0.05]]
    expect(diezmar(r, 1)).toHaveLength(4)
    expect(escalarAnillo(cuadro(0, 0, 2), [1, 1], 0.5)).toEqual([[0.5, 0.5], [1.5, 0.5], [1.5, 1.5], [0.5, 1.5]])
  })
  it('una rodela tiene tantos festones como se pide', () => {
    expect(rutaRodela(0, 0, 10, 18).match(/A/g)).toHaveLength(18)
    expect(anilloCircular(0, 0, 1, 4)[0]![1]).toBeCloseTo(-1, 9)
  })
})

describe('capas de una comuna', () => {
  it('sin punto queda sin dato; con banda que cruza trae recorte', () => {
    expect(apilarNivel(undefined, [20, 30, 40, 50])).toEqual({ nivel: null, cruce: null })
    const p = apilarNivel({ p10: 38, p50: 42, p90: 47 }, [20, 30, 40, 50])
    expect(p.nivel).toBe(3)
    expect(p.cruce?.nivel).toBe(2)
  })
  it('los labios se apilan en orden de política, proporcionales al aporte y con topes', () => {
    const ap = [
      { politicaId: 'b', indice: 1, delta: 0.1 },
      { politicaId: 'a', indice: 0, delta: -2 },
      { politicaId: 'c', indice: 2, delta: 0 },
    ]
    const l = apilarLabios(ap, new Set(['a', 'b']), 2, 1, 8)
    expect(l.map((x) => x.politicaId)).toEqual(['a', 'b'])
    expect(l[0]).toMatchObject({ ancho: 8, corrimiento: 8, pegada: true })
    expect(l[1]).toMatchObject({ ancho: 1, corrimiento: 9 })
  })
  it('una hoja despegada sale desde su lugar y las pegadas cierran el hueco', () => {
    const ap = [
      { politicaId: 'a', indice: 0, delta: 1 },
      { politicaId: 'b', indice: 1, delta: 1 },
    ]
    const l = apilarLabios(ap, new Set(['b']), 1, 1, 4)
    expect(l[0]).toMatchObject({ pegada: false, corrimiento: 4 })
    expect(l[1]).toMatchObject({ pegada: true, corrimiento: 4 })
    expect(apilarLabios([], new Set(), 1, 1, 4)).toEqual([])
  })
  it('el hash es estable', () => {
    expect(hash01('abc')).toBe(hash01('abc'))
    expect(hash01('abc')).toBeGreaterThanOrEqual(0)
    expect(hash01('abc')).toBeLessThan(1)
  })

})
