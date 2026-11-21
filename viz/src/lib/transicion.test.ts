import { describe, expect, it } from 'vitest'
import {
  OPCIONES_TRANSICION_DEFECTO,
  comunasMasTransformadas,
  cursorDeProgreso,
  easeOutCubic,
  easeOutExpo,
  estadoTransformacionEnCursor,
  featuresDeFocos,
  interpolarBanda,
  interpolarMapaPuntos,
  lineal,
  resolverProgreso,
} from './transicion'
import { leerTransformaciones } from './validate'
import type { Punto } from './data'
import type { TransformacionEscenario } from './types'

describe('curvas y progreso de transición', () => {
  it('respeta extremos [0, 1] y salta directo a 1 con prefers-reduced-motion', () => {
    expect(lineal(-0.5)).toBe(0)
    expect(lineal(1.5)).toBe(1)
    expect(easeOutCubic(0)).toBe(0)
    expect(easeOutCubic(1)).toBe(1)
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5)
    expect(easeOutExpo(0)).toBe(0)
    expect(easeOutExpo(1)).toBe(1)
    expect(resolverProgreso(0.2, true, 'ease-out-cubic')).toBe(1)
    expect(resolverProgreso(0, false, 'lineal')).toBe(0)
  })

  it('convierte progreso continuo de años en cursor acotado', () => {
    expect(cursorDeProgreso(2.25, 11)).toEqual({ indiceBase: 2, indiceSiguiente: 3, fraccion: 0.25 })
    expect(cursorDeProgreso(15, 11)).toEqual({ indiceBase: 10, indiceSiguiente: 10, fraccion: 0 })
    expect(cursorDeProgreso(-1, 11)).toEqual({ indiceBase: 0, indiceSiguiente: 1, fraccion: 0 })
    expect(cursorDeProgreso(0, 0)).toEqual({ indiceBase: 0, indiceSiguiente: 0, fraccion: 0 })
  })
})

describe('interpolación de bandas', () => {
  it('mantiene p10 <= p50 <= p90 y preserva comunas sin origen', () => {
    const desde = new Map<string, Punto>([['13101', { p10: 18, p50: 20, p90: 22 }]])
    const hasta = new Map<string, Punto>([
      ['13101', { p10: 14, p50: 16, p90: 18 }],
      ['13105', { p10: 20, p50: 22, p90: 24 }],
    ])
    const mid = interpolarMapaPuntos(desde, hasta, 0.5, { curva: 'lineal' })
    const s = mid.get('13101')!
    expect(s.p50).toBeCloseTo(18)
    expect(s.p10).toBeLessThanOrEqual(s.p50)
    expect(s.p50).toBeLessThanOrEqual(s.p90)
    expect(mid.get('13105')).toEqual({ p10: 20, p50: 22, p90: 24 })

    const b = interpolarBanda({ p10: 10, p50: 12, p90: 14 }, { p10: 10, p50: 12, p90: 14 }, 0.5)
    expect(b).toEqual({ p10: 10, p50: 12, p90: 14 })
  })
})

describe('estado de transformación y GeoJSON de focos', () => {
  const tr: TransformacionEscenario = {
    referencia: 'base',
    variable: 'pm25_anual',
    tipo: 'reduccion_emisiones',
    max_abs_delta: 4.0,
    epicentro: { lat: -33.6, lon: -70.7 },
    bbox: [-71.0, -33.8, -70.5, -33.4],
    intensidad_regional: [0.2, 0.6, 1.0],
    comunas_foco: [
      { codigo: '13105', direccion: 'mejora', delta_p50: [-0.8, -2.4, -4.0], incertidumbre: [0.3, 0.6, 0.9], intensidad: [0.2, 0.6, 1.0] },
      { codigo: '13101', direccion: 'mejora', delta_p50: [-0.1, -0.4, -0.8], incertidumbre: [0.1, 0.2, 0.3], intensidad: [0.02, 0.1, 0.2] },
    ],
  }

  it('mantiene modo ninguno por defecto y filtra focos bajo el umbral al activar', () => {
    expect(OPCIONES_TRANSICION_DEFECTO.modo).toBe('ninguno')
    const apagado = estadoTransformacionEnCursor(tr, { indiceBase: 1, indiceSiguiente: 2, fraccion: 0.5 })
    expect(apagado.activo).toBe(false)

    const activo = estadoTransformacionEnCursor(
      tr,
      { indiceBase: 1, indiceSiguiente: 2, fraccion: 0.5 },
      { modo: 'focos', umbralFoco: 0.16 },
    )
    expect(activo.activo).toBe(true)
    expect(activo.intensidadRegional).toBeCloseTo(0.8)
    expect(activo.focos).toHaveLength(1)
    expect(activo.focos[0]!.codigo).toBe('13105')
    expect(activo.focos[0]!.deltaP50).toBeCloseTo(-3.2)
    expect(comunasMasTransformadas(activo, 1)[0]!.codigo).toBe('13105')

    const geo = featuresDeFocos(activo, new Map([['13105', [-70.66, -33.56]]]))
    expect(geo).toHaveLength(1)
    expect(geo[0]!.geometry.coordinates).toEqual([-70.66, -33.56])
  })

  it('valida transformaciones opcionales defensivamente', () => {
    const ok = leerTransformaciones(
      {
        referencia_por_defecto: 'base',
        por_escenario: { 'con-propuesta-lena-zona-b': tr },
      },
      3,
    )
    expect(ok?.por_escenario['con-propuesta-lena-zona-b']?.comunas_foco).toHaveLength(2)
    expect(leerTransformaciones({ por_escenario: { malo: { ...tr, intensidad_regional: [0.1] } } }, 3)).toBeUndefined()
  })
})
