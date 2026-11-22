import { describe, expect, it } from 'vitest'
import { lugarDe, modoDe, PESTANAS, seccionesDe } from './pestanas'

const todo = { aire: true, seguridad: true, crecimiento: true, lena: true, urbano: true, validacion: true }

describe('pestañas y secciones', () => {
  it('son cinco, y todas menos el resumen explican de qué tratan', () => {
    expect(PESTANAS.map((p) => p.id)).toEqual(['resumen', 'clima', 'legal', 'social', 'referencias'])
    expect(PESTANAS.filter((p) => !p.titulo || !p.subtitulo).map((p) => p.id)).toEqual(['resumen'])
  })
  it('una sección sin datos no aparece', () => {
    expect(seccionesDe('social', todo).map((s) => s.id)).toEqual(['seguridad', 'crecimiento', 'urbano', 'aportes'])
    expect(seccionesDe('social', { seguridad: true }).map((s) => s.id)).toEqual(['seguridad', 'aportes'])
    expect(seccionesDe('referencias', {}).map((s) => s.id)).toEqual(['fuentes'])
  })
})

describe('modoDe', () => {
  it('el resumen es el índice general y lo legal son los planes', () => {
    expect(modoDe('resumen', undefined, [])).toEqual({ vista: 'riesgo', papel: null, seccion: null })
    expect(modoDe('legal', undefined, []).vista).toBe('plan')
  })
  it('cada sección lleva a su vista y a su variable', () => {
    const clima = seccionesDe('clima', todo)
    expect(modoDe('clima', 'aire', clima)).toEqual({ vista: 'riesgo', papel: 'aire', seccion: 'aire' })
    expect(modoDe('clima', 'lena', clima).vista).toBe('lena')
    expect(modoDe('social', 'urbano', seccionesDe('social', todo)).vista).toBe('mudanzas')
    expect(modoDe('referencias', 'validacion', seccionesDe('referencias', todo)).vista).toBe('prueba')
  })
  it('si la sección pedida no existe abre la primera disponible', () => {
    expect(modoDe('social', 'urbano', seccionesDe('social', { crecimiento: true })).seccion).toBe('crecimiento')
    expect(modoDe('referencias', 'validacion', seccionesDe('referencias', {}))).toEqual({ vista: 'fuentes', papel: null, seccion: 'fuentes' })
  })
  it('el detalle de cada variable tiene su lugar', () => {
    expect(lugarDe('aire')).toEqual({ pestana: 'clima', seccion: 'aire' })
    expect(lugarDe('crecimiento')).toEqual({ pestana: 'social', seccion: 'crecimiento' })
  })
})
