import { describe, expect, it } from 'vitest'
import { ordenarPorPeso } from './variables'

const v = (id: string) => ({ id })
const catalogo = ['pm25_anual', 'seguridad', 'crecimiento_poblacion', 'sequia_futura', 'escasez_hidrica', 'red_electrica'].map(v)

describe('orden de las variables por peso', () => {
  it('pone primero la de más peso y las de peso 0 al final: con industria el aire ya no va primero', () => {
    const pesos = { pm25_anual: 0, seguridad: 5, crecimiento_poblacion: 8, red_electrica: 10 }
    expect(ordenarPorPeso(catalogo, pesos).map((x) => x.id)).toEqual([
      'red_electrica',
      'crecimiento_poblacion',
      'seguridad',
      'pm25_anual',
      'sequia_futura',
      'escasez_hidrica',
    ])
  })

  it('en un empate conserva el orden del catálogo y no toca la lista recibida', () => {
    const pesos = { escasez_hidrica: 5, seguridad: 5, pm25_anual: 5 }
    expect(ordenarPorPeso(catalogo, pesos).map((x) => x.id).slice(0, 3)).toEqual(['pm25_anual', 'seguridad', 'escasez_hidrica'])
    expect(catalogo[0]!.id).toBe('pm25_anual')
  })
})
