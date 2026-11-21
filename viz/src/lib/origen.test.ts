import { describe, expect, it } from 'vitest'
import { seleccionarOrigenes } from './origen'
import { validarOrigenAire } from './validate'

describe('seleccionarOrigenes', () => {
  const lista = [
    { origen: 'a', fraccion: 0.4 },
    { origen: 'b', fraccion: 0.1 },
    { origen: 'c', fraccion: 0.05 },
    { origen: 'd', fraccion: 0.12 },
    { origen: 'e', fraccion: 0.02 },
    { origen: 'f', fraccion: 0.03 },
    { origen: 'g', fraccion: 0.04 },
    { origen: 'h', fraccion: 0.01 },
  ]
  it('separa la parte propia y deja las 6 mayores de las demás, ordenadas', () => {
    const r = seleccionarOrigenes(lista, 'a')!
    expect(r.propia).toBe(0.4)
    expect(r.otros.map((o) => o.origen)).toEqual(['d', 'b', 'c', 'g', 'f', 'e'])
    expect(r.resto).toBeCloseTo(1 - 0.4 - 0.12 - 0.1 - 0.05 - 0.04 - 0.03 - 0.02)
  })
  it('si la comuna no aparece como origen, propia es null', () => {
    const r = seleccionarOrigenes(lista, 'zzz')!
    expect(r.propia).toBeNull()
    expect(r.otros).toHaveLength(6)
  })
  it('sin datos devuelve null y no inventa nada', () => {
    expect(seleccionarOrigenes(undefined, 'a')).toBeNull()
    expect(seleccionarOrigenes([], 'a')).toBeNull()
    expect(seleccionarOrigenes([{ origen: 'b', fraccion: 0 }], 'a')).toBeNull()
  })
  it('el resto nunca es negativo', () => {
    const r = seleccionarOrigenes([{ origen: 'a', fraccion: 0.7 }, { origen: 'b', fraccion: 0.3 }], 'a')!
    expect(r.resto).toBe(0)
  })
})

describe('validarOrigenAire', () => {
  const ok = { base: { x: [{ origen: 'x', fraccion: 0.5 }, { origen: 'y', fraccion: 0.2 }] } }
  it('acepta la forma correcta, también con suma menor que 1', () => {
    const r = validarOrigenAire(ok)
    expect(r.ok).toBe(true)
  })
  it('rechaza lo que no es objeto', () => {
    const r = validarOrigenAire([1])
    expect(r.ok).toBe(false)
  })
  it('rechaza fracción fuera de 0 a 1, origen vacío y listas que no son listas, con mensaje claro', () => {
    const malo = {
      base: {
        x: [{ origen: 'x', fraccion: 1.2 }],
        y: [{ origen: '', fraccion: 0.1 }],
        z: 'no',
      },
    }
    const r = validarOrigenAire(malo)
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.errores.join('\n')).toContain('origen_aire.base.x[0]')
      expect(r.errores.join('\n')).toContain('origen_aire.base.y[0]')
      expect(r.errores.join('\n')).toContain('origen_aire.base.z debe ser una lista')
    }
  })
  it('rechaza sumas mayores que 1', () => {
    const r = validarOrigenAire({ base: { x: [{ origen: 'a', fraccion: 0.7 }, { origen: 'b', fraccion: 0.6 }] } })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.errores[0]).toContain('suman')
  })
})
