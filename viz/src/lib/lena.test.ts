import { describe, expect, it } from 'vitest'
import { agregarZonas, leerLena, radioDisco, type ComunaLena } from './lena'

const fila = (codigo: string, zona: 'A' | 'B', toneladas: number | null, poblacion: number): ComunaLena => ({
  codigo,
  nombre: codigo,
  zona,
  toneladas,
  poblacion,
})

describe('agregarZonas', () => {
  it('suma toneladas y población por zona y calcula partes; sin dato no suma cero, se anota', () => {
    const z = agregarZonas([fila('a', 'A', 10, 800), fila('b', 'B', 30, 200), fila('c', 'A', null, 0)])
    expect(z.A.toneladas).toBe(10)
    expect(z.B.parteEmisiones).toBe(0.75)
    expect(z.A.partePoblacion).toBe(0.8)
    expect(z.A.sinDato).toEqual(['c'])
    expect(z.A.comunas).toBe(2)
  })
})

describe('leerLena', () => {
  const raw = {
    meta: { anio: 2023, fuente: 'RETC', zonas: 'D.S. 31/2016' },
    comunas: [
      { codigo: '1', nombre: 'Uno', zona: 'A', toneladas: 5, poblacion: 10 },
      { codigo: '2', nombre: 'Dos', zona: 'B', toneladas: null, poblacion: 5 },
      { codigo: '3', nombre: 'Tres', zona: 'C', toneladas: 1, poblacion: 1 },
      { codigo: '4', nombre: 'Cuatro', zona: 'B', toneladas: -2, poblacion: 1 },
      { codigo: 5, nombre: '<b>x</b>', zona: 'A', toneladas: 1, poblacion: 1 },
    ],
  }
  it('descarta filas inválidas y conserva el sin dato', () => {
    const l = leerLena(raw)!
    expect(l.comunas.map((c) => c.codigo)).toEqual(['1', '2'])
    expect(l.comunas[1]!.toneladas).toBeNull()
    expect(l.anio).toBe(2023)
  })
  it('la zona de la simulación manda y se anotan las diferencias', () => {
    const l = leerLena(raw, new Map([['1', 'B' as const]]))!
    expect(l.comunas[0]!.zona).toBe('B')
    expect(l.discrepancias).toEqual(['Uno'])
  })
  it('null si no es un archivo de leña', () => {
    expect(leerLena(null)).toBeNull()
    expect(leerLena({ comunas: [] })).toBeNull()
  })
})

describe('radioDisco', () => {
  it('el área es proporcional a las toneladas', () => {
    expect(radioDisco(100, 100, 10)).toBe(10)
    expect(radioDisco(25, 100, 10)).toBe(5)
    expect(radioDisco(0, 100, 10)).toBe(0)
  })
})
