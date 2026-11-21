import { describe, expect, it } from 'vitest'
import { bordesPasos, cortesPara, cruceBanda, escalaRecorte, nivel, papelNivel, pasoDiferencia, tablaPara, textoNivel } from './niveles'

describe('nivel', () => {
  it('corta en 20, 30, 40 y 50 con el corte en el nivel de abajo', () => {
    expect([0, 20, 20.01, 30, 35, 40, 45, 50, 50.1, 90].map((v) => nivel(v))).toEqual([0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
  })
  it('usa seis pasos relativos a la norma para medias anuales y la tabla de invierno para el resto', () => {
    expect(cortesPara({ id: 'pm25_anual', nombre: 'PM2,5 media anual' })).toEqual([10, 15, 20, 23, 26])
    expect(tablaPara({ id: 'pm25_anual', nombre: 'x' }, 25)).toEqual({ cortes: [12.5, 18.8, 25, 28.8, 32.5], norma: 25 })
    expect(tablaPara({ id: 'pm25_invierno', nombre: 'x' }, 25).norma).toBeNull()
    expect([5, 12, 18, 21, 24, 30].map((v) => nivel(v, cortesPara({ id: 'pm25_anual', nombre: '' })))).toEqual([0, 1, 2, 3, 4, 5])
    expect(cortesPara({ id: 'pm25_invierno', nombre: 'PM2,5 de invierno' })).toEqual([20, 30, 40, 50])
    expect(nivel(22.5, cortesPara({ id: 'x', nombre: 'Media anual' }))).toBe(3)
  })
  it('asigna papeles: seis niveles directo, cinco saltan el paso intercalado', () => {
    expect([0, 1, 2, 3, 4, 5].map((i) => papelNivel(i, [10, 15, 20, 23, 26]))).toEqual([0, 1, 2, 3, 4, 5])
    expect([0, 1, 2, 3, 4].map((i) => papelNivel(i, [20, 30, 40, 50]))).toEqual([0, 1, 2, 4, 5])
    expect(textoNivel(3, [10, 15, 20, 23.5, 26])).toBe('20 a 23,5')
  })
  it('nombra los rangos en español', () => {
    expect([0, 1, 2, 3, 4].map((i) => textoNivel(i))).toEqual(['hasta 20', '20 a 30', '30 a 40', '40 a 50', 'más de 50'])
  })
})

describe('cruceBanda', () => {
  it('es null si la banda queda dentro del nivel', () => {
    expect(cruceBanda({ p10: 41, p50: 45, p90: 49 })).toBeNull()
    expect(cruceBanda({ p10: 51, p50: 60, p90: 70 })).toBeNull()
  })
  it('elige el lado con más banda más allá del corte', () => {
    expect(cruceBanda({ p10: 39, p50: 43, p90: 55 })!.nivel).toBe(4)
    expect(cruceBanda({ p10: 33, p50: 42, p90: 51 })!.nivel).toBe(2)
  })
  it('un p10 justo en el corte ya alcanza el nivel de abajo', () => {
    expect(cruceBanda({ p10: 40, p50: 44, p90: 48 })!.nivel).toBe(2)
  })
  it('el recorte crece con el ancho de la banda y tiene topes', () => {
    const angosta = escalaRecorte({ p10: 39, p50: 41, p90: 43 })
    const ancha = escalaRecorte({ p10: 32, p50: 41, p90: 50 })
    expect(ancha).toBeGreaterThan(angosta)
    expect(escalaRecorte({ p10: 0, p50: 10, p90: 100 })).toBe(0.55)
    expect(escalaRecorte({ p10: 10, p50: 10, p90: 10 })).toBe(0.25)
  })
})

describe('pasoDiferencia', () => {
  it('es 0 bajo el umbral y firma según cuál dirección es mejor', () => {
    expect(pasoDiferencia(0.1, 6, 'menor')).toBe(0)
    expect(pasoDiferencia(-1, 6, 'menor')).toBe(-1)
    expect(pasoDiferencia(3, 6, 'menor')).toBe(2)
    expect(pasoDiferencia(6, 6, 'menor')).toBe(3)
    expect(pasoDiferencia(6, 6, 'mayor')).toBe(-3)
    expect(pasoDiferencia(Number.NaN, 6, 'menor')).toBe(0)
  })
  it('da los bordes de la leyenda', () => {
    expect(bordesPasos(6)).toEqual([0.2, 2, 4, 6])
  })
})
