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

describe('resumirPruebas: population and housing blocks', () => {
  const filas = resumirPruebas({
    bloques: [
      { ...b('poblacion', { rmse_modelo: 18471.9, rmse_sin_cambio: 15046.3, rmse_cerrado: 16903.6, rmse_proyeccion_ine: 18391.1 }), unidad: 'personas' },
      { ...b('vivienda', { rmse_modelo: 4334.8, rmse_pivote_permisos: 5049.5, rmse_radiacion: 14900 }), unidad: 'personas' },
    ],
  })
  it('shows them in persons, with readable titles and rivals', () => {
    expect(filas.map((f) => [f.id, f.formato, f.resultado])).toEqual([
      ['poblacion', 'personas', 'pierde'],
      ['vivienda', 'personas', 'gana'],
    ])
    expect(filas[0]!.titulo).toBe('Población por comuna, 2017 a 2024')
    expect(filas[0]!.rival.nombre).toBe('suponer que nada cambia')
    expect(filas[1]!.rival.nombre).toBe('destinos ajustados por permisos')
  })
})

describe('resumirPruebas: unified validation (make validate)', () => {
  const fila = (o: Partial<import('./types').PruebaValidacion>) => ({
    variable: 'Aire',
    prueba: 'PM2,5 por estación 2022-2024 desde 2019',
    metrica: 'RMSE µg/m³',
    modelo: 1.905,
    sin_cambio: 2.401,
    tendencia: 4.243,
    gana: 'modelo',
    ...o,
  })
  const v: Validacion = {
    bloques: [b('hogares', { rmse_modelo: 4334.8, rmse_repetir_2012_2017: 5054 }), b('vivienda', { rmse_modelo: 4334.8, rmse_pivote_permisos: 5049.5 })],
    tolerancia: 0.02,
    pruebas: [
      fila({}),
      fila({ variable: 'Población', prueba: 'Población por comuna 2024 desde 2017', metrica: 'RMSE personas', modelo: 16903.6, sin_cambio: 15046.3, tendencia: null, gana: 'sin_cambio' }),
      fila({ variable: 'Seguridad', prueba: 'Delitos 2024 a 1 año', metrica: 'RMSE log (≈ error relativo)', modelo: 0.1, sin_cambio: 0.099, tendencia: 0.13, gana: 'empate' }),
    ],
  }

  it('shows only the unified tests, so no test is counted twice', () => {
    const filas = resumirPruebas(v)
    expect(filas.map((f) => f.titulo)).toEqual([
      'Aire: PM2,5 por estación 2022-2024 desde 2019',
      'Población: Población por comuna 2024 desde 2017',
      'Seguridad: Delitos 2024 a 1 año',
    ])
  })

  it('takes the winner as computed by make validate and names the best alternative', () => {
    const [aire, pob, seg] = resumirPruebas(v)
    expect(aire).toMatchObject({ resultado: 'gana', rival: { nombre: 'sin cambio', valor: 2.401 }, formato: 'aire' })
    expect(pob).toMatchObject({ resultado: 'pierde', rival: { nombre: 'sin cambio', valor: 15046.3 }, formato: 'personas' })
    expect(seg).toMatchObject({ resultado: 'empata', formato: 'pct' })
    expect(contarPruebas(resumirPruebas(v))).toEqual({ gana: 1, empata: 1, pierde: 1 })
  })
})
