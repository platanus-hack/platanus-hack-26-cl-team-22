import { describe, expect, it } from 'vitest'
import { leerValidacion } from './validate'

describe('leerValidacion', () => {
  it('keeps the unit, metric and warning text of each block', () => {
    const v = leerValidacion({
      fuente: 'results/aire_calibracion.json',
      niveles_2024: { rmse_modelo: 4.29, rmse_persistencia: 1.91 },
      poblacion: {
        unidad: 'personas',
        metrica: 'Población por comuna en 2024',
        aviso: 'Nadie le gana a sin cambio',
        rmse_modelo: 18471.9,
        rmse_sin_cambio: 15046.3,
      },
    })
    const pob = v?.bloques.find((b) => b.id === 'poblacion')
    expect(pob?.unidad).toBe('personas')
    expect(pob?.metrica).toBe('Población por comuna en 2024')
    expect(pob?.aviso).toBe('Nadie le gana a sin cambio')
    expect(pob?.valores.map((x) => x.clave)).toEqual(['rmse_modelo', 'rmse_sin_cambio'])
  })

  it('leaves the unit empty for blocks that do not declare one', () => {
    const v = leerValidacion({ niveles_2024: { rmse_modelo: 4.29 } })
    expect(v?.bloques[0]?.unidad).toBeUndefined()
  })

  it('still drops a block with text but no numbers', () => {
    expect(leerValidacion({ solo_texto: { unidad: 'personas', aviso: 'x' } })).toBeUndefined()
  })
})

describe('leerValidacion: unified tests from make validate', () => {
  const fila = { variable: 'Aire', prueba: 'PM2,5 2022-2024', metrica: 'RMSE µg/m³', modelo: 1.9, sin_cambio: 2.4, tendencia: null, gana: 'modelo', notas: 'x' }

  it('keeps well-formed rows and the tie tolerance, and drops malformed ones', () => {
    const v = leerValidacion({ pruebas: [fila, { variable: 'Mal', modelo: 'uno' }, 'texto'], tolerancia: 0.02 })
    expect(v?.pruebas).toEqual([{ variable: 'Aire', prueba: 'PM2,5 2022-2024', metrica: 'RMSE µg/m³', modelo: 1.9, sin_cambio: 2.4, tendencia: null, gana: 'modelo' }])
    expect(v?.tolerancia).toBe(0.02)
  })

  it('does not turn the rows array into an old-style block', () => {
    expect(leerValidacion({ pruebas: [fila] })?.bloques).toEqual([])
  })
})
