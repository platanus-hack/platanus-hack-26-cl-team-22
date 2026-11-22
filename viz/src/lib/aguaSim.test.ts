import { describe, expect, it } from 'vitest'
import { leerAgua } from './agua'
import { decadaDe, periodoDe, resumirSim, sortearDecadas } from './aguaSim'

// 1980–2017: años normales alrededor de 100 hasta 2009 y una megasequía alrededor de 45 desde 2010.
const anual = Array.from({ length: 38 }, (_, i) => (i < 30 ? 90 + (i % 5) * 5 : 40 + (i % 3) * 5))
const agua = leerAgua(
  {
    meta: { periodo: [1980, 2017], base: [1980, 2009], sequia: [2010, 2017] },
    estaciones: [
      { codigo: '5710001', nombre: 'Río Maipo En El Manzano', rio: 'Río Maipo', lon: -70.38, lat: -33.59, anual, regimen: Array(12).fill(1), medio: 90, base: 100, sequia: 45 },
      { codigo: '5722002', nombre: 'Río Mapocho En Los Almendros', rio: 'Río Mapocho', lon: -70.45, lat: -33.37, anual: anual.map((v, i) => (i === 35 ? null : v / 10)), regimen: Array(12).fill(1), medio: 9, base: 10, sequia: 4.5 },
    ],
  },
  null,
)!
const [maipo, mapocho] = agua.estaciones as [(typeof agua.estaciones)[0], (typeof agua.estaciones)[0]]

describe('décadas posibles de caudal', () => {
  it('cada escenario sortea solo de su período', () => {
    expect(periodoDe(agua, 'megasequia')).toEqual([30, 31, 32, 33, 34, 35, 36, 37])
    expect(periodoDe(agua, 'normal')).toHaveLength(30)
    expect(periodoDe(agua, 'registro')).toHaveLength(38)
    const d = sortearDecadas(agua, 'megasequia', 11, 200)
    expect(d.sorteo).toHaveLength(200 * 11)
    expect([...d.sorteo].every((i) => i >= 30 && i <= 37)).toBe(true)
  })
  it('con la misma semilla da lo mismo, y con otra cambia', () => {
    const a = sortearDecadas(agua, 'registro', 11, 100, 7)
    expect([...sortearDecadas(agua, 'registro', 11, 100, 7).sorteo]).toEqual([...a.sorteo])
    expect([...sortearDecadas(agua, 'registro', 11, 100, 8).sorteo]).not.toEqual([...a.sorteo])
  })
  it('los años salen en bloques seguidos, como en los datos', () => {
    const d = sortearDecadas(agua, 'registro', 12, 50)
    for (let r = 0; r < 50; r++) for (let b = 0; b < 4; b++) {
      const i = r * 12 + b * 3
      expect(d.sorteo[i + 1]).toBe(d.sorteo[i]! + 1)
      expect(d.sorteo[i + 2]).toBe(d.sorteo[i]! + 2)
    }
  })
  it('si sigue la megasequía casi todos los años son críticos; si vuelve lo normal, ninguno', () => {
    const seca = resumirSim(agua, maipo, sortearDecadas(agua, 'megasequia', 11))
    const normal = resumirSim(agua, maipo, sortearDecadas(agua, 'normal', 11))
    const todo = resumirSim(agua, maipo, sortearDecadas(agua, 'registro', 11))
    expect(seca.aniosCriticos).toBeCloseTo(11)
    expect(seca.racha3).toBe(1)
    expect(normal.aniosCriticos).toBe(0)
    expect(normal.racha3).toBe(0)
    expect(todo.aniosCriticos).toBeGreaterThan(normal.aniosCriticos)
    expect(todo.aniosCriticos).toBeLessThan(seca.aniosCriticos)
    expect(seca.p50.every((v) => v < 0.6)).toBe(true)
    expect(normal.p10.every((v, i) => v <= normal.p50[i]! && normal.p50[i]! <= normal.p90[i]!)).toBe(true)
    expect(todo.probCritico.every((p) => p >= 0 && p <= 1)).toBe(true)
  })
  it('una década concreta usa los mismos años reales en todos los ríos', () => {
    const d = sortearDecadas(agua, 'registro', 11)
    const a = decadaDe(agua, maipo, d, 137)
    const b = decadaDe(agua, mapocho, d, 137)
    expect(a).toHaveLength(11)
    // mismas proporciones salvo en el año que al Mapocho le falta (usa su promedio)
    const iguales = a.filter((v, t) => Math.abs(v - b[t]!) < 1e-9).length
    expect(iguales).toBeGreaterThanOrEqual(8)
    expect(decadaDe(agua, maipo, d, 137 + d.replicas)).toEqual(a)
  })
  it('un año sin dato no rompe el sorteo: usa el promedio del período', () => {
    const d = sortearDecadas(agua, 'megasequia', 11)
    expect(decadaDe(agua, mapocho, d, 3).every((v) => Number.isFinite(v) && v > 0)).toBe(true)
  })
})
