import { describe, expect, it } from 'vitest'
import { aportePorEstado, credibilidadSin, filtrarLicitaciones, leerLicitaciones, leerProyectos, montoDe, ordenInicial, pagina, pesosCortos, puntosCredibilidad, urlSeia } from './aportes'
import { fmt } from './format'

const proyectos = {
  comunas: [
    {
      codigo: '13302',
      inversion_evaluada: 3,
      proyectos: [
        { expediente_id: '111', nombre: 'Parque solar', titular: 'Sol SpA', descripcion_tipologia: 'Centrales', inversion_musd: 12.5, fecha_presentacion: '2020-03-01', url_ficha: 'https://seia.sea.gob.cl/expediente/expediente.php?id_expediente=111', aporte: 1 },
        { expediente_id: '222', nombre: 'Bodega', titular: 'Log SA', descripcion_tipologia: 'Bodegas', inversion_musd: null, fecha_presentacion: '2024-07-10', url_ficha: 'https://otro.sitio.cl/ficha', aporte: 1 },
        { expediente_id: 'x<y', nombre: 'Malo', fecha_presentacion: '2021-01-01' },
        { expediente_id: '333', nombre: '', fecha_presentacion: '2021-01-01' },
      ],
    },
  ],
}

const lics = {
  codigo: '13101',
  anio: 2024,
  max_n_efectivo: 40,
  afecta_modelo: true,
  credibilidad_media: 0.852,
  tasa_adjudicacion: 0.9,
  licitaciones: [
    { codigo_externo: 'A-1', nombre: 'Luminarias', estado: 'adjudicada', sector: 'obras', monto_estimado_clp: 9e6, monto_adjudicado_clp: 8e6, numero_oferentes: 3, aporte_credibilidad: 0.00013 },
    { codigo_externo: 'A-2', nombre: 'Cámaras', estado: 'fallida', sector: 'seguridad', monto_estimado_clp: 2e9, monto_adjudicado_clp: null, numero_oferentes: 0, aporte_credibilidad: -0.0012 },
    { codigo_externo: 'A-3', nombre: 'Aseo', estado: 'adjudicada', sector: 'servicios', monto_estimado_clp: null, monto_adjudicado_clp: null, numero_oferentes: 1, aporte_credibilidad: 0.00013 },
    { codigo_externo: 'A-4', nombre: 'En curso', estado: 'abierta', sector: 'otros', monto_estimado_clp: 5e5, aporte_credibilidad: 0 },
    { codigo_externo: 'A-5', nombre: 'Rara', estado: 'inventada', aporte_credibilidad: 9 },
  ],
}

describe('proyectos SEIA de una comuna', () => {
  it('lee los válidos, del más reciente al más antiguo, y descarta los que no calzan', () => {
    const r = leerProyectos(proyectos, '13302')!
    expect(r.map((p) => p.id)).toEqual(['222', '111'])
    expect(r[1]!.monto).toBe(12.5)
    expect(r[0]!.monto).toBeNull()
  })
  it('solo enlaza fichas del SEIA por https', () => {
    const r = leerProyectos(proyectos, '13302')!
    expect(r[1]!.url).toContain('https://seia.sea.gob.cl/')
    expect(r[0]!.url).toBeNull()
    expect(urlSeia('javascript:alert(1)')).toBeNull()
    expect(urlSeia('http://seia.sea.gob.cl/x')).toBeNull()
    expect(urlSeia('https://seia.sea.gob.cl.evil.com/x')).toBeNull()
  })
  it('sin la comuna o sin archivo devuelve null', () => {
    expect(leerProyectos(proyectos, '13101')).toBeNull()
    expect(leerProyectos(null, '13302')).toBeNull()
  })
})

describe('licitaciones de una comuna', () => {
  const c = leerLicitaciones(lics)!
  it('lee conteos, credibilidad y descarta estados desconocidos', () => {
    expect(c.licitaciones).toHaveLength(4)
    expect(c.conteo).toEqual({ adjudicada: 2, fallida: 1, abierta: 1 })
    expect(c.afectaModelo).toBe(true)
    expect(c.credibilidad).toBe(0.852)
    expect(c.tope).toBe(40)
    expect(leerLicitaciones({})).toBeNull()
  })
  it('filtra por estado y ordena por monto, con lo sin monto al final', () => {
    expect(filtrarLicitaciones(c.licitaciones, null, 'monto').map((l) => l.codigo)).toEqual(['A-2', 'A-1', 'A-4', 'A-3'])
    expect(filtrarLicitaciones(c.licitaciones, 'adjudicada', 'monto').map((l) => l.codigo)).toEqual(['A-1', 'A-3'])
    expect(filtrarLicitaciones(c.licitaciones, null, 'aporte')[0]!.codigo).toBe('A-2')
    expect(montoDe(c.licitaciones[1]!)).toBe(2e9)
  })
  it('a igual aporte, ordena primero la de mayor monto', () => {
    expect(filtrarLicitaciones(c.licitaciones, 'adjudicada', 'aporte').map((l) => l.codigo)).toEqual(['A-1', 'A-3'])
  })
  it('parte ordenada por aporte solo si la comuna entra al modelo', () => {
    expect(ordenInicial(true)).toBe('aporte')
    expect(ordenInicial(false)).toBe('monto')
  })
  it('dice cuánto sería la credibilidad sin esa licitación, y nada si no la movió', () => {
    expect(credibilidadSin(c, c.licitaciones[0]!)).toBeCloseTo(0.852 - 0.00013, 10)
    expect(credibilidadSin(c, c.licitaciones[3]!)).toBeNull()
    const fuera = leerLicitaciones({ ...lics, afecta_modelo: false })!
    expect(credibilidadSin(fuera, fuera.licitaciones[0]!)).toBeNull()
  })
  it('hay un aporte por estado', () => {
    expect(aportePorEstado(c)).toEqual({ adjudicada: 0.00013, fallida: -0.0012, abierta: 0 })
  })
  it('una comuna fuera del modelo no trae credibilidad', () => {
    const fuera = leerLicitaciones({ ...lics, afecta_modelo: false, credibilidad_media: null })!
    expect(fuera.afectaModelo).toBe(false)
    expect(fuera.credibilidad).toBeNull()
  })
})

describe('página y montos', () => {
  it('parte la lista y acota el número de página', () => {
    const xs = Array.from({ length: 13 }, (_, i) => i)
    expect(pagina(xs, 0, 6)).toEqual({ filas: [0, 1, 2, 3, 4, 5], paginas: 3, actual: 0 })
    expect(pagina(xs, 9, 6)).toEqual({ filas: [12], paginas: 3, actual: 2 })
    expect(pagina([], 0, 6).paginas).toBe(1)
  })
  it('escribe los pesos en la escala que se lee', () => {
    expect(pesosCortos(2e9, fmt)).toBe('$ 2.000 millones')
    expect(pesosCortos(5_062_910, fmt)).toBe('$ 5,1 millones')
    expect(pesosCortos(850_000, fmt)).toBe('$ 850 mil')
    expect(pesosCortos(null, fmt)).toBe('sin monto')
  })
  it('escribe el aporte en puntos de credibilidad, con signo', () => {
    expect(puntosCredibilidad(0.00013, fmt)).toBe(`+${fmt(0.013, 3)} pt`)
    expect(puntosCredibilidad(-0.0012, fmt)).toBe(`−${fmt(0.12, 3)} pt`)
    expect(puntosCredibilidad(0, fmt)).toBe(`${fmt(0, 3)} pt`)
  })
})
