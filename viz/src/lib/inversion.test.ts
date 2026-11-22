import { describe, expect, it } from 'vitest'
import { indicadoresInversion, indicadorSequia, leerInversion } from './inversion'

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
