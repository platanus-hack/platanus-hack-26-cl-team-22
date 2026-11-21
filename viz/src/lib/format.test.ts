import { describe, expect, it } from 'vitest'
import { fmt, fmtBanda, safeUrl, slug } from './format'
import { validarSimulacion } from './validate'
import ejemplo from '../../ejemplo/simulacion.json'

type Editable = { trayectorias: any; flujos?: unknown; aportes?: unknown }
const copia = () => structuredClone(ejemplo) as unknown as Editable

describe('format', () => {
  it('usa coma decimal', () => {
    expect(fmt(41.38)).toBe('41,4')
    expect(fmtBanda(41, 38, 45, 'µg/m³', 0)).toBe('41 (38–45) µg/m³')
  })
  it('solo acepta http y https', () => {
    expect(safeUrl('https://ejemplo.cl/a')).toBe('https://ejemplo.cl/a')
    expect(safeUrl('javascript:alert(1)')).toBeNull()
    expect(safeUrl('data:text/html,hola')).toBeNull()
    expect(safeUrl('/relativa')).toBeNull()
    expect(safeUrl(42)).toBeNull()
  })
  it('normaliza nombres', () => {
    expect(slug('Ñuñoa')).toBe('nunoa')
    expect(slug('San José de Maipo')).toBe('san-jose-de-maipo')
  })
})

describe('validarSimulacion', () => {
  it('acepta el ejemplo', () => {
    expect(validarSimulacion(ejemplo).ok).toBe(true)
  })
  it('rechaza series con largo distinto al de años', () => {
    const malo = copia()
    malo.trayectorias.base.cerrillos.pm25_invierno.p50.pop()
    expect(validarSimulacion(malo).ok).toBe(false)
  })
  it('no falla si faltan claves opcionales', () => {
    const m = copia()
    delete m.flujos
    delete m.aportes
    const r = validarSimulacion(m)
    expect(r.ok && r.data.flujos === undefined && r.data.aportes === undefined).toBe(true)
  })
  it('rechaza basura', () => {
    expect(validarSimulacion(null).ok).toBe(false)
    expect(validarSimulacion({}).ok).toBe(false)
  })
})
