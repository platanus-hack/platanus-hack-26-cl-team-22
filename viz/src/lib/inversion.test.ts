import { describe, expect, it } from 'vitest'
import { comoVariables, indicadoresInversion, indicadorSequia, leerInversion, sumarIndicadores, unionIndicadores } from './inversion'
import { calcularRiesgo } from './riesgo'

const codigos = Array.from({ length: 30 }, (_, i) => String(13101 + i))
const archivo = (extra: Record<string, unknown> = {}) => ({
  meta: {},
  indicadores: [
    { id: 'escasez_hidrica', nombre: 'Escasez hídrica', que: 'Años con decreto', unidad: 'años', mejor: 'menor', fuente: 'DGA', periodo: '2008–2023' },
    { id: 'red_electrica', nombre: 'Red eléctrica', que: 'Capacidad', unidad: 'MVA', mejor: 'mayor', fuente: 'CEN', periodo: '2026' },
    { id: 'sequia_futura', nombre: 'Sequía futura', que: 'x', unidad: 'índice', mejor: 'menor', fuente: 'ARClim', periodo: '2035–2065' },
  ],
  comunas: codigos.map((codigo, i) => ({ codigo, valores: { escasez_hidrica: i % 4, red_electrica: i * 10, sequia_futura: i < 9 ? 1 : null } })),
  ...extra,
})
const clima = (anios: number[]) => ({
  por_escenario: {
    ssp245: {
      anios,
      riesgos: { hidrico: { drought_periods: { unidad: 'pp', por_comuna: Object.fromEntries(codigos.map((c, i) => [c, { p10: anios.map(() => 0), p50: anios.map((_, t) => i + t), p90: anios.map(() => 9) }])) } } },
    },
  },
})

describe('indicadores de inversión', () => {
  it('lee los que sirven para comparar y descarta el que vale lo mismo en todas o cubre pocas comunas', () => {
    const r = leerInversion(archivo())
    expect(r.map((x) => x.id)).toEqual(['escasez_hidrica', 'red_electrica'])
    expect(r[0]!.valores.size).toBe(30)
    expect(r[0]!.origen).toBe('real')
  })
  it('el riesgo respeta el sentido: menos decretos es mejor, más capacidad es mejor', () => {
    const [escasez, red] = leerInversion(archivo()) as [ReturnType<typeof leerInversion>[0], ReturnType<typeof leerInversion>[0]]
    expect(escasez.riesgo.get('13101')!).toBeLessThan(escasez.riesgo.get('13104')!) // 0 años frente a 3
    expect(red.riesgo.get('13130')!).toBeLessThan(red.riesgo.get('13101')!) // 290 MVA frente a 0
  })
  it('ignora lo que no es un número, un código o un sentido válido', () => {
    const r = leerInversion(
      archivo({
        indicadores: [{ id: 'red_electrica', nombre: 'Red', mejor: 'cualquiera' }, { id: '<b>', nombre: 'x', mejor: 'menor' }, { id: 'escasez_hidrica', nombre: 'Escasez', mejor: 'menor' }],
        comunas: [...codigos.map((codigo, i) => ({ codigo, valores: { escasez_hidrica: i % 3 } })), { codigo: 'x', valores: { escasez_hidrica: 99 } }, { codigo: '13199', valores: { escasez_hidrica: 'muchos' } }],
      }),
    )
    expect(r).toHaveLength(1)
    expect(r[0]!.valores.size).toBe(30)
    expect(leerInversion(null)).toEqual([])
  })
  it('la sequía futura sale del año pedido del modelo climático', () => {
    const s = indicadorSequia(clima([2026, 2027, 2028]), 2028)!
    expect(s.valores.get('13101')).toBe(2)
    expect(s.valores.get('13130')).toBe(31)
    expect(s.origen).toBe('simulado')
    expect(s.riesgo.get('13101')!).toBeLessThan(s.riesgo.get('13130')!)
    expect(indicadorSequia(clima([2026]), 2040)).toBeNull()
    expect(indicadorSequia(undefined, 2026)).toBeNull()
  })
  it('junta simulados y reales en orden, sin repetir la sequía', () => {
    const ids = indicadoresInversion(leerInversion(archivo()), clima([2026]), 2026).map((x) => x.id)
    expect(ids).toEqual(['sequia_futura', 'escasez_hidrica', 'red_electrica'])
    expect(indicadoresInversion(leerInversion(archivo()), null, 2026).map((x) => x.id)).toEqual(['escasez_hidrica', 'red_electrica'])
  })
})

describe('los indicadores dentro del índice', () => {
  const inds = indicadoresInversion(leerInversion(archivo()), clima([2026, 2027]), 2026)
  const filas = codigos.map((codigo) => ({ codigo, valores: { pm25_anual: 20 } as Record<string, number | undefined> }))

  it('se vuelven variables del índice con su nombre, unidad y sentido', () => {
    expect(comoVariables(inds)).toEqual([
      { id: 'sequia_futura', nombre: 'Sequía futura', unidad: 'pp', mejor: 'menor' },
      { id: 'escasez_hidrica', nombre: 'Escasez hídrica', unidad: 'años', mejor: 'menor' },
      { id: 'red_electrica', nombre: 'Red eléctrica', unidad: 'MVA', mejor: 'mayor' },
    ])
  })

  it('suma el valor de cada indicador a la fila de su comuna, sin tocar lo que ya tenía', () => {
    const con = sumarIndicadores(filas, inds)
    expect(con[3]!.valores).toEqual({ pm25_anual: 20, sequia_futura: 3, escasez_hidrica: 3, red_electrica: 30 })
    expect(filas[3]!.valores).toEqual({ pm25_anual: 20 })
  })

  it('con peso solo en la red eléctrica, el índice ordena por la red: más capacidad, menos riesgo', () => {
    const r = calcularRiesgo(sumarIndicadores(filas, inds), [{ id: 'pm25_anual', nombre: 'Aire', unidad: 'µg/m³', mejor: 'menor' }, ...comoVariables(inds)], { red_electrica: 10 })
    expect(r.filas[0]!.codigo).toBe(codigos[29])
    expect(r.usadas).toEqual(['red_electrica'])
  })

  it('une los indicadores de todos los años sin repetir: sequía cuenta aunque falte en algún año', () => {
    const reales = leerInversion(archivo())
    const porAnio = [2025, 2026, 2027].map((a) => indicadoresInversion(reales, clima([2026, 2027]), a))
    expect(porAnio[0]!.map((x) => x.id)).toEqual(['escasez_hidrica', 'red_electrica'])
    expect(unionIndicadores(porAnio).map((x) => x.id)).toEqual(['sequia_futura', 'escasez_hidrica', 'red_electrica'])
    expect(unionIndicadores([])).toEqual([])
  })
})
