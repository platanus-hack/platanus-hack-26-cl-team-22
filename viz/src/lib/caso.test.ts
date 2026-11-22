import { describe, expect, it } from 'vitest'
import { componerCaso, MAX_PREGUNTAS, validarPreguntas, aplicarAjustes, ESQUEMA_INTERPRETACION, LARGO_CASO_MAX, pedirInterpretacion, validarInterpretacion, type Interpretacion } from './caso'

const caso = 'Busco departamento para mi familia; mi hijo tiene asma y trabajo de noche.'

const valida = {
  ajustes: [
    { variable: 'pm25_anual', grado: 10, cita: 'mi hijo tiene asma' },
    { variable: 'seguridad', grado: 8, cita: 'trabajo de noche' },
  ],
  indicadores: ['dias_sobre_norma_diaria_pm25'],
  no_medido: ['colegios'],
}

describe('validarInterpretacion', () => {
  it('accepts adjustments whose quotes appear in the case', () => {
    const r = validarInterpretacion(valida, caso)
    expect(r?.ajustes.map((a) => [a.variable, a.grado])).toEqual([
      ['pm25_anual', 10],
      ['seguridad', 8],
    ])
    expect(r?.indicadores).toEqual(['dias_sobre_norma_diaria_pm25'])
    expect(r?.no_medido).toEqual(['colegios'])
  })

  it('drops an adjustment whose quote is not in the case (no invented reasons)', () => {
    const r = validarInterpretacion({ ...valida, ajustes: [{ variable: 'pm25_anual', grado: 10, cita: 'vive cerca de una fábrica' }] }, caso)
    expect(r?.ajustes).toEqual([])
  })

  it('matches quotes ignoring accents, case and spacing', () => {
    const r = validarInterpretacion({ ...valida, ajustes: [{ variable: 'pm25_anual', grado: 10, cita: 'MI HIJO  tiene ASMA' }] }, caso)
    expect(r?.ajustes).toHaveLength(1)
  })

  it('drops anything outside the closed catalog', () => {
    const r = validarInterpretacion(
      {
        ajustes: [
          { variable: 'precio_vivienda', grado: 10, cita: 'mi hijo tiene asma' },
          { variable: 'pm25_anual', grado: 7, cita: 'mi hijo tiene asma' },
        ],
        indicadores: ['inventado'],
        no_medido: ['colegios', 'otra_cosa'],
      },
      caso,
    )
    expect(r?.ajustes).toEqual([])
    expect(r?.indicadores).toEqual([])
    expect(r?.no_medido).toEqual(['colegios'])
  })

  it('keeps only one adjustment per variable', () => {
    const r = validarInterpretacion(
      { ...valida, ajustes: [valida.ajustes[0], { variable: 'pm25_anual', grado: 3, cita: 'trabajo de noche' }] },
      caso,
    )
    expect(r?.ajustes).toHaveLength(1)
    expect(r?.ajustes[0]!.grado).toBe(10)
  })

  it('rejects something that is not an interpretation', () => {
    expect(validarInterpretacion('hola', caso)).toBeNull()
    expect(validarInterpretacion({ ajustes: 'x' }, caso)).toBeNull()
  })

  it('never carries numbers about comunas: unknown fields are dropped', () => {
    const r = validarInterpretacion({ ...valida, ranking: [{ comuna: 'Ñuñoa', riesgo: 3 }] }, caso) as Interpretacion & { ranking?: unknown }
    expect(r?.ranking).toBeUndefined()
  })
})

describe('aplicarAjustes', () => {
  it('replaces the grade of each adjusted variable and leaves the rest', () => {
    const base = { pm25_anual: 8, seguridad: 8, crecimiento_poblacion: 3 }
    const r = validarInterpretacion(valida, caso)!
    expect(aplicarAjustes(base, r)).toEqual({ pm25_anual: 10, seguridad: 8, crecimiento_poblacion: 3 })
    expect(base.pm25_anual).toBe(8)
  })

  it('ignores adjustments the person switched off', () => {
    const base = { pm25_anual: 8, seguridad: 3, crecimiento_poblacion: 3 }
    const r = validarInterpretacion(valida, caso)!
    expect(aplicarAjustes(base, r, new Set(['seguridad']))).toEqual({ pm25_anual: 10, seguridad: 3, crecimiento_poblacion: 3 })
  })
})

describe('ESQUEMA_INTERPRETACION', () => {
  it('is a strict JSON schema with only catalog values and no numeric fields about comunas', () => {
    const s = ESQUEMA_INTERPRETACION as Record<string, any>
    expect(s.additionalProperties).toBe(false)
    expect(s.required).toEqual(['ajustes', 'indicadores', 'no_medido', 'preguntas'])
    const ajuste = s.properties.ajustes.items
    expect(ajuste.additionalProperties).toBe(false)
    expect(ajuste.properties.variable.enum).toEqual(['pm25_anual', 'seguridad', 'crecimiento_poblacion'])
    expect(ajuste.properties.grado.enum).toEqual([0, 3, 5, 8, 10])
    expect(JSON.stringify(s)).not.toMatch(/comuna/)
  })

  it('caps the case length', () => {
    expect(LARGO_CASO_MAX).toBeGreaterThan(100)
  })
})

describe('pedirInterpretacion', () => {
  const pedido = { caso, perfil: 'Comprar una vivienda', prioridades: { pm25_anual: 8 } }
  const fetchQue = (status: number, cuerpo: unknown) =>
    (async () => new Response(JSON.stringify(cuerpo), { status })) as unknown as typeof fetch

  it('posts the case and returns the validated interpretation', async () => {
    let enviado: unknown = null
    const f = (async (_url: string, init: RequestInit) => {
      enviado = JSON.parse(String(init.body))
      return new Response(JSON.stringify(valida), { status: 200 })
    }) as unknown as typeof fetch
    const r = await pedirInterpretacion('http://localhost:8787/interpretar', pedido, f)
    expect(enviado).toEqual(pedido)
    expect(r?.ajustes).toHaveLength(2)
  })

  it('returns null when the server fails or answers something else', async () => {
    expect(await pedirInterpretacion('http://x/interpretar', pedido, fetchQue(503, { error: 'x' }))).toBeNull()
    expect(await pedirInterpretacion('http://x/interpretar', pedido, fetchQue(200, 'hola'))).toBeNull()
  })
})

describe('follow-up questions', () => {
  it('keeps at most two distinct, short questions', () => {
    const q = validarPreguntas({ preguntas: ['¿Es para vivir o para una empresa?', '¿Es para vivir o para una empresa?', '¿Hay niños o personas con asma?', '¿Una tercera pregunta?'] })
    expect(q).toEqual(['¿Es para vivir o para una empresa?', '¿Hay niños o personas con asma?'])
    expect(q.length).toBeLessThanOrEqual(MAX_PREGUNTAS)
  })

  it('drops non-strings, empty and overlong questions, and anything that is not the expected shape', () => {
    expect(validarPreguntas({ preguntas: [3, '', 'x'.repeat(200), null] })).toEqual([])
    expect(validarPreguntas('hola')).toEqual([])
    expect(validarPreguntas({})).toEqual([])
  })

  it('appends only the answered questions and stays within the case limit', () => {
    expect(componerCaso('Busco casa', ['¿Hay niños?', '¿Trabajan de noche?'], ['sí, una de 4 años', ' '])).toBe('Busco casa\n¿Hay niños? sí, una de 4 años')
    expect(componerCaso('Busco casa', ['¿Hay niños?'], [])).toBe('Busco casa')
    expect(componerCaso('a'.repeat(400), ['q'.repeat(90), 'q'.repeat(90)], ['r'.repeat(300), 'r'.repeat(300)]).length).toBeLessThanOrEqual(LARGO_CASO_MAX)
  })

  it('comes back inside the interpretation, so one call reads the case and asks what is missing', () => {
    const r = validarInterpretacion({ ajustes: [], indicadores: [], no_medido: [], preguntas: ['¿Es para vivir o para una empresa?', 'x', '¿Hay niños o personas con asma?', '¿Una tercera pregunta?'] }, caso)
    expect(r?.preguntas).toEqual(['¿Es para vivir o para una empresa?', '¿Hay niños o personas con asma?'])
    expect(ESQUEMA_INTERPRETACION.required).toContain('preguntas')
    expect(validarInterpretacion({ ajustes: [], indicadores: [], no_medido: [] }, caso)?.preguntas).toEqual([])
  })
})
