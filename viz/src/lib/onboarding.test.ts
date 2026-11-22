import { describe, expect, it, vi } from 'vitest'
import { PERFILES } from './caso'
import { limpiarGuia, pedirGuia, urlGuia } from './guia'
import { CASOS, casoDe, explicar, fueraDeRango, gradoDe, leerCaso, limpiarCriterio, prioridadesDe, resolverLimites } from './onboarding'
import { calcularRiesgo } from './riesgo'
import type { Variable } from './types'

const vars: Variable[] = [
  { id: 'pm25_anual', nombre: 'Aire', unidad: 'µg/m³', mejor: 'menor' },
  { id: 'crecimiento_poblacion', nombre: 'Crecimiento', unidad: '%', mejor: 'mayor' },
]
const filas = [
  { codigo: 'a', valores: { pm25_anual: 10, crecimiento_poblacion: 9 } },
  { codigo: 'b', valores: { pm25_anual: 20, crecimiento_poblacion: 5 } },
  { codigo: 'c', valores: { pm25_anual: 30, crecimiento_poblacion: 1 } },
]
const nombre = (c: string) => ({ a: 'Lampa', b: 'Buin', c: 'Renca' })[c] ?? c

describe('leer el caso', () => {
  it('reconoce el perfil por palabras clave, con o sin tildes (respaldo cuando Claude no responde)', () => {
    expect(leerCaso('Quiero instalar una central HIDROELÉCTRICA de pasada')).toBe('energia')
    expect(leerCaso('Busco depto para mi familia')).toBe('familia')
    expect(leerCaso('abrir una bodega de logística')).toBe('industria')
    expect(leerCaso('Mis papás ya están mayores y quieren mudarse')).toBe('mayor')
    expect(leerCaso('Soy estudiante y busco arriendo barato')).toBe('joven')
    expect(leerCaso('Quiero comprar un departamento para arrendarlo y que se valorice')).toBe('inversion')
    expect(leerCaso('Quiero abrir un local comercial con más clientes')).toBe('emprendedor')
    expect(leerCaso('Busco oficina para mi startup')).toBe('empresario')
  })
  it('las palabras que antes confundían el perfil ya no lo hacen', () => {
    expect(leerCaso('Quiero instalar la casa matriz de mi empresa de software.')).toBe('empresario')
    expect(leerCaso('Busco oficina para el departamento de logística de mi empresa.')).toBe('industria')
    expect(leerCaso('Quiero poner paneles solares en mi casa nueva para la familia.')).toBe('familia')
  })
  it('lo que no reconoce o viene vacío es una evaluación general', () => {
    expect(leerCaso('asdf qwer')).toBe('general')
    expect(leerCaso('   ')).toBe('general')
  })
  it('cada caso trae entre cinco y siete criterios contando los tres simulados', () => {
    for (const id of PERFILES.map((p) => p.id)) {
      const n = casoDe(id).referencia.length + 3
      expect(n).toBeGreaterThanOrEqual(5)
      expect(n).toBeLessThanOrEqual(7)
    }
  })
})

describe('grados y prioridades', () => {
  it('lleva cualquier prioridad al grado más cercano', () => {
    expect([gradoDe(0), gradoDe(2), gradoDe(6), gradoDe(9), gradoDe(10)]).toEqual([0, 3, 5, 8, 10])
  })
  it('solo da prioridades para variables que existen; las desconocidas parten en medio', () => {
    expect(prioridadesDe(casoDe('industria'), ['crecimiento_poblacion', 'otra'])).toEqual({ crecimiento_poblacion: 8, otra: 5 })
  })
  it('en industria y energía el aire no pesa: pesan seguridad y crecimiento', () => {
    expect(casoDe('industria').prioridades.pm25_anual).toBe(0)
    expect(casoDe('energia').prioridades.pm25_anual).toBe(0)
  })
  it('nueve perfiles con los pesos aprobados (aire / seguridad / crecimiento)', () => {
    const tabla = Object.fromEntries(CASOS.map((c) => [c.id, [c.prioridades.pm25_anual, c.prioridades.seguridad, c.prioridades.crecimiento_poblacion]]))
    expect(tabla).toEqual({
      familia: [10, 8, 3],
      mayor: [10, 8, 0],
      joven: [3, 8, 5],
      inversion: [3, 5, 10],
      emprendedor: [0, 8, 10],
      empresario: [3, 5, 8],
      industria: [0, 5, 8],
      energia: [0, 5, 8],
      general: [5, 5, 5],
    })
  })
})

describe('rangos', () => {
  const valores = filas.map((f) => f.valores)
  it('un rango fijo da su límite; uno relativo sale de los datos del año', () => {
    expect(resolverLimites({ pm25_anual: 'norma' }, vars, valores)).toEqual({ pm25_anual: 20, crecimiento_poblacion: null })
    const seg: Variable = { id: 'seguridad', nombre: 'Seguridad', unidad: '', mejor: 'menor' }
    const v = [{ seguridad: 400 }, { seguridad: 100 }, { seguridad: 300 }, { seguridad: 200 }]
    expect(resolverLimites({ seguridad: 'mitad' }, [seg], v).seguridad).toBe(200)
    expect(resolverLimites({ seguridad: 'inventado' }, [seg], v).seguridad).toBeNull()
  })
  it('marca fuera de rango según el sentido de la variable; el borde y la falta de dato no cuentan', () => {
    const lim = { pm25_anual: 20, crecimiento_poblacion: 5 }
    expect(fueraDeRango({ pm25_anual: 20, crecimiento_poblacion: 5 }, lim, vars)).toEqual([])
    expect(fueraDeRango({ pm25_anual: 20.1, crecimiento_poblacion: 4.9 }, lim, vars)).toEqual(['pm25_anual', 'crecimiento_poblacion'])
    expect(fueraDeRango({}, lim, vars)).toEqual([])
  })
  it('un criterio propio se acota y no se repite', () => {
    expect(limpiarCriterio('  Riesgo   sísmico ', [])).toBe('Riesgo sísmico')
    expect(limpiarCriterio('riesgo sismico', ['Riesgo sísmico'])).toBeNull()
    expect(limpiarCriterio('   ', [])).toBeNull()
    expect(limpiarCriterio('x'.repeat(90), [])).toHaveLength(40)
  })
})

describe('explicar', () => {
  const pesos = { pm25_anual: 3, crecimiento_poblacion: 8 }
  const r = calcularRiesgo(filas, vars, pesos)
  it('nombra a la primera, en qué destaca según lo que más pesa, y a las que siguen', () => {
    expect(explicar(r, vars, pesos, nombre, { sinDatos: ['Caudal medio del río'] })).toBe(
      'Lampa es la de menor riesgo para ti: la mejor de la región en crecimiento. Le siguen Buin y Renca. Aún sin datos: caudal medio del río.',
    )
  })
  it('con rangos solo recomienda comunas que los cumplen, y avisa si ninguna lo hace', () => {
    expect(explicar(r, vars, pesos, nombre, { dentro: new Set(['b', 'c']) })).toMatch(/^Buin es la de menor riesgo dentro de tus rangos/)
    expect(explicar(r, vars, pesos, nombre, { dentro: new Set() })).toMatch(/Ninguna comuna cumple/)
  })
  it('sin datos lo dice', () => {
    expect(explicar(calcularRiesgo([], vars, {}), vars, {}, nombre)).toMatch(/No hay datos/)
  })
})

describe('guía del intermediario', () => {
  it('se queda solo con el texto, sin saltos y acotado', () => {
    expect(limpiarGuia({ texto: '  Hola\n mundo ', otra: { cosa: 1 } })).toEqual({ texto: 'Hola mundo' })
    expect(limpiarGuia({ texto: 'x'.repeat(5000) })!.texto.length).toBeLessThanOrEqual(600)
  })

  it('al acortar corta en el fin de una frase, nunca a mitad de palabra', () => {
    const frases = 'María Pinto encabeza. Le siguen Alhué y El Monte. '
    expect(limpiarGuia({ texto: frases + 'no mide precio del suelo '.repeat(40) })!.texto).toBe(frases.trim())
    const sinPunto = limpiarGuia({ texto: 'palabra '.repeat(200) })!.texto
    expect(sinPunto.length).toBeLessThanOrEqual(600)
    expect(sinPunto).toMatch(/ palabra…$/)
  })
  it('rechaza lo que no calza', () => {
    expect(limpiarGuia({ texto: 5 })).toBeNull()
    expect(limpiarGuia({ texto: '   ' })).toBeNull()
    expect(limpiarGuia('hola')).toBeNull()
  })
  it('solo acepta un intermediario por https, o local por http', () => {
    expect(urlGuia('https://x.onrender.com/guia')).toBe('https://x.onrender.com/guia')
    expect(urlGuia('http://localhost:8787/guia')).toBe('http://localhost:8787/guia')
    expect(urlGuia('http://x.com/guia')).toBeNull()
    expect(urlGuia('javascript:alert(1)')).toBeNull()
    expect(urlGuia(undefined)).toBeNull()
  })
  it('si el intermediario falla, no hay guía y no se cae', async () => {
    const pedido = { perfil: 'empresa', contexto: 'x', prioridades: {}, anio: 2026, top: [] }
    expect(await pedirGuia('https://x/guia', pedido, vi.fn().mockRejectedValue(new Error('red')))).toBeNull()
    expect(await pedirGuia('https://x/guia', pedido, vi.fn().mockResolvedValue({ ok: false }))).toBeNull()
    const ok = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ texto: 'Lampa conviene.' }) })
    expect(await pedirGuia('https://x/guia', pedido, ok)).toEqual({ texto: 'Lampa conviene.' })
  })
})
