import { describe, expect, it } from 'vitest'
import { anchoRio, cauceDe, caucesMedidos, claveCauce, estacionDeComuna, factorAnio, leerAgua, regimenDe, tonoCambio, variabilidad } from './agua'

const estacion = (extra: Record<string, unknown> = {}) => ({
  codigo: '5710001',
  nombre: 'Río Maipo En El Manzano',
  rio: 'Río Maipo',
  lon: -70.38,
  lat: -33.59,
  altitud: 850,
  comuna: '13203',
  subcuenca: 'Rio Maipo Medio',
  anual: [100, null, 80, 60, 40],
  regimen: [180, 150, 100, 70, 60, 60, 60, 65, 75, 100, 150, 190],
  medio: 70,
  base: 90,
  sequia: 50,
  cambio: -44.4,
  cv: 0.6,
  ...extra,
})
const archivo = (estaciones: unknown[]) => ({ meta: { fuente: 'DGA', licencia: 'CC0', descarga: '2026-11-21', periodo: [2013, 2017], base: [2013, 2014], sequia: [2015, 2017] }, estaciones })
const rio = (props: Record<string, unknown>, coordinates: unknown) => ({ type: 'Feature', properties: props, geometry: { type: 'LineString', coordinates } })

describe('leerAgua', () => {
  it('lee estaciones y ríos válidos', () => {
    const a = leerAgua(archivo([estacion()]), {
      features: [rio({ nombre: 'Río Maipo', clase: 'river', estacion: '5710001' }, [[-70.3, -33.6], [-70.4, -33.6]])],
    })!
    expect(a.anios).toEqual([2013, 2014, 2015, 2016, 2017])
    expect(a.estaciones[0]!.anual).toEqual([100, null, 80, 60, 40])
    expect(a.rios).toHaveLength(1)
    expect(a.rios[0]!.estacion).toBe('5710001')
  })
  it('descarta lo que no calza en vez de mostrarlo', () => {
    const a = leerAgua(
      archivo([
        estacion(),
        estacion({ codigo: '5710002', lon: 10 }), // fuera de la región
        estacion({ codigo: '5710003', anual: [1, 2] }), // largo distinto al período
        estacion({ codigo: '5710004', medio: -3 }),
        estacion({ codigo: '<img>' }),
        estacion(), // repetida
      ]),
      null,
    )!
    expect(a.estaciones.map((e) => e.codigo)).toEqual(['5710001'])
    expect(a.rios).toEqual([])
  })
  it('un valor anual inválido queda como año sin dato', () => {
    const a = leerAgua(archivo([estacion({ anual: [100, 'x', -5, 60, 40] })]), null)!
    expect(a.estaciones[0]!.anual).toEqual([100, null, null, 60, 40])
  })
  it('el enlace en vivo solo vale si es una página de estación de caudalrio.cl', () => {
    const lee = (vivo: unknown) => leerAgua(archivo([estacion({ vivo })]), null)!.estaciones[0]!.vivo
    expect(lee('https://caudalrio.cl/caudal/rio-maipo-en-el-manzano-05710001-k')).toBe('https://caudalrio.cl/caudal/rio-maipo-en-el-manzano-05710001-k')
    expect(lee('javascript:alert(1)')).toBeNull()
    expect(lee('https://caudalrio.cl.evil.example/caudal/x')).toBeNull()
    expect(lee('https://caudalrio.cl/caudal/x?y=<script>')).toBeNull()
  })
  it('un río que apunta a una estación desconocida queda sin estación, y uno con un solo vértice se descarta', () => {
    const a = leerAgua(archivo([estacion()]), {
      features: [rio({ nombre: 'Estero X', clase: 'stream', estacion: '999999' }, [[-70.3, -33.6], [-70.4, -33.6]]), rio({ nombre: 'Corto' }, [[-70.3, -33.6]])],
    })!
    expect(a.rios).toHaveLength(1)
    expect(a.rios[0]!.estacion).toBeNull()
    expect(a.rios[0]!.clase).toBe('stream')
  })
  it('sin estaciones válidas no hay nada que mostrar', () => {
    expect(leerAgua(archivo([]), null)).toBeNull()
    expect(leerAgua('x', null)).toBeNull()
    expect(leerAgua({ meta: { periodo: [2017, 2013] }, estaciones: [estacion()] }, null)).toBeNull()
  })
})

describe('por dónde pasa cada río', () => {
  const conCauces = (cauces: unknown) => leerAgua({ ...archivo([estacion(), estacion({ codigo: '5730008', rio: 'Quebrada Ramón', medio: 0.2 })]), cauces }, null)!
  it('el nombre del mapa y el de la estación se reconocen como el mismo cauce', () => {
    expect(claveCauce('Quebrada de Ramón')).toBe(claveCauce('Quebrada Ramon'))
    expect(claveCauce('Estero El Arrayán')).toBe(claveCauce('Estero Arrayan'))
    expect(claveCauce('Estero Puangue')).toBe(claveCauce('Río Puangue'))
    expect(claveCauce('Río Maipo')).not.toBe(claveCauce('Río Mapocho'))
  })
  it('lee las comunas en orden y descarta las que no son un código', () => {
    const a = conCauces([{ nombre: 'Río Maipo', clase: 'river', estacion: '5710001', comunas: ['13203', '13202', 'x', '13203'], largo_km: 255.8 }, { nombre: '' }])
    expect(a.cauces).toHaveLength(1)
    expect(a.cauces[0]).toMatchObject({ comunas: ['13203', '13202'], largoKm: 255.8 })
    expect(cauceDe(a, a.porCodigo.get('5710001')!)?.nombre).toBe('Río Maipo')
    expect(cauceDe(a, a.porCodigo.get('5730008')!)).toBeNull()
  })
  it('el mapa busca cada río medido por el nombre con que viene mapeado', () => {
    const a = conCauces([{ nombre: 'Quebrada de Ramón', clase: 'stream', estacion: '5730008', comunas: ['13114'] }])
    const c = caucesMedidos(a.estaciones, a.cauces)
    expect(c).toHaveLength(2)
    expect(c.find((x) => x.estacion.codigo === '5730008')!.nombres[0]).toBe('Quebrada de Ramón')
    expect(c.find((x) => x.estacion.codigo === '5710001')!.nombres).toContain('Río Maipo')
  })
})

describe('lecturas del caudal', () => {
  it('la caída en la megasequía tiene cuatro grados', () => {
    expect(tonoCambio(null)).toBe('sin')
    expect(tonoCambio(-5)).toBe('estable')
    expect(tonoCambio(-20)).toBe('baja')
    expect(tonoCambio(-40)).toBe('fuerte')
    expect(tonoCambio(-60)).toBe('critica')
  })
  it('distingue un río de deshielo de uno de lluvia por el mes de más agua', () => {
    expect(regimenDe([180, 150, 100, 70, 60, 60, 60, 65, 75, 100, 150, 190])).toMatchObject({ mesAlto: 11, tipo: 'deshielo' })
    expect(regimenDe([1, 1, 1, 2, 4, 8, 9, 7, 4, 2, 1, 1])).toMatchObject({ mesAlto: 6, tipo: 'lluvia', mesBajo: 0 })
  })
  it('lee la variabilidad', () => {
    expect(variabilidad(0.3)).toBe('Caudal parejo')
    expect(variabilidad(0.8)).toBe('Caudal variable')
    expect(variabilidad(1.6)).toBe('Caudal muy variable')
    expect(variabilidad(null)).toBe('Sin dato')
  })
  it('el factor de un año compara con el medio, y un año sin dato no encoge el río', () => {
    const e = leerAgua(archivo([estacion()]), null)!.estaciones[0]!
    expect(factorAnio(e, 0)).toBeCloseTo(100 / 70)
    expect(factorAnio(e, 1)).toBe(1)
    expect(factorAnio(e, null)).toBe(1)
  })
  it('el ancho del cauce crece con el caudal, con piso y techo', () => {
    expect(anchoRio(100, 'river')).toBeGreaterThan(anchoRio(5, 'river'))
    expect(anchoRio(0, 'stream')).toBeGreaterThanOrEqual(1.4)
    expect(anchoRio(1e6, 'river')).toBe(12)
    expect(anchoRio(null, 'river')).toBeGreaterThan(anchoRio(null, 'stream'))
  })
  it('elige la estación de más caudal de una comuna', () => {
    const a = leerAgua(archivo([estacion(), estacion({ codigo: '5710009', medio: 5 }), estacion({ codigo: '5722002', comuna: '13115', medio: 6 })]), null)!
    expect(estacionDeComuna(a.estaciones, '13203')?.codigo).toBe('5710001')
    expect(estacionDeComuna(a.estaciones, '13115')?.codigo).toBe('5722002')
    expect(estacionDeComuna(a.estaciones, '13101')).toBeNull()
    expect(estacionDeComuna(a.estaciones, null)).toBeNull()
  })
})
