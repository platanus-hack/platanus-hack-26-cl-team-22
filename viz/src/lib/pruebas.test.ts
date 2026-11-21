import { describe, expect, it } from 'vitest'
import { comparar, contarPruebas, resumirPruebas } from './pruebas'
import type { Validacion } from './types'

const b = (id: string, o: Record<string, number>) => ({ id, valores: Object.entries(o).map(([clave, valor]) => ({ clave, valor })) })

describe('comparar', () => {
  it('empata dentro del 5 % y, fuera, gana quien tiene menos error', () => {
    expect(comparar(0.9, 0.91)).toBe('empata')
    expect(comparar(4.29, 1.91)).toBe('pierde')
    expect(comparar(4335, 5054)).toBe('gana')
    expect(comparar(0, 0)).toBe('empata')
  })
})

describe('resumirPruebas', () => {
  const v: Validacion = {
    bloques: [
      b('cambio_2017_2023', { observado_media: -3.19, rmse_modelo: 0.9, rmse_sin_cambio: 3.32, rmse_mismo_cambio_en_todas: 0.91 }),
      b('niveles_2024', { rmse_modelo: 4.29, rmse_persistencia: 1.91, rmse_media_otras_estaciones: 2.87 }),
      b('ajuste_2023', { estaciones: 10, r2: 0.55 }),
      b('seguridad', { modelo_1_anio: 0.085, modelo_2_anios: 0.1078, persistencia_2023: 0.0739, persistencia_2022: 0.124, tendencia_2022_2023: 0.1305 }),
      b('hogares', { rmse_modelo: 4334.8, rmse_nadie_se_muda: 7716.2, rmse_repetir_2012_2017: 5054 }),
    ],
  }
  const filas = resumirPruebas(v)
  it('enfrenta al modelo con la mejor alternativa de cada prueba', () => {
    expect(filas.map((f) => [f.id, f.resultado])).toEqual([
      ['cambio_2017_2023', 'empata'],
      ['niveles_2024', 'pierde'],
      ['seguridad-2', 'gana'],
      ['seguridad-1', 'pierde'],
      ['hogares', 'gana'],
    ])
    expect(filas[0]!.rival).toEqual({ nombre: 'el mismo cambio en todas', valor: 0.91 })
    expect(filas[2]!.rival.nombre).toBe('repetir 2022')
  })
  it('salta los bloques sin error que comparar y cuenta el marcador', () => {
    expect(filas.some((f) => f.id === 'ajuste_2023')).toBe(false)
    expect(contarPruebas(filas)).toEqual({ gana: 2, empata: 1, pierde: 2 })
  })
})
