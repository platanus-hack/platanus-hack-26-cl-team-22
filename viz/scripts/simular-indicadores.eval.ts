/**
 * Simulation run before the four extra indicators enter the app: for each profile, the five lowest-risk
 * communes with the three simulated variables only (the weights approved before) against the seven-variable
 * index (3 active per profile), in the first and the last simulated year. No model calls.
 *   npm run evaluar -- simular-indicadores
 * Writes docs/simulacion-indicadores.md.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterAll, describe, expect, it } from 'vitest'
import datos from '../datos/simulacion.json'
import { PERFILES } from '../src/lib/caso'
import { punto, variablesConDato } from '../src/lib/data'
import { comoVariables, indicadoresInversion, leerInversion, sumarIndicadores, type IndicadorInversion } from '../src/lib/inversion'
import { calcularRiesgo } from '../src/lib/riesgo'
import { escenarioInicial } from '../src/lib/scenario'
import type { Simulacion } from '../src/lib/types'

const data = datos as unknown as Simulacion
const reales = leerInversion(JSON.parse(readFileSync(resolve(__dirname, '../public/datos/inversion.json'), 'utf8')))
const ids = [...variablesConDato(data)]
const escenario = escenarioInicial(data.escenarios).id
const nombre = new Map(data.comunas.map((c) => [c.codigo, c.nombre]))
const anios = data.meta.anios

/** The three-variable weights approved before the indicators (S2 in odd/tasks/perfiles-indicadores.md). */
const ANTES: Record<string, [number, number, number]> = {
  familia: [10, 8, 3], mayor: [10, 8, 0], joven: [3, 8, 5], inversion: [3, 5, 10], emprendedor: [0, 8, 10],
  empresario: [3, 5, 8], industria: [0, 5, 8], energia: [0, 5, 8], general: [5, 5, 5],
}

function indice(i: number, conIndicadores: boolean, pesos: Record<string, number>) {
  const base = data.comunas.map((c) => ({ codigo: c.codigo, valores: Object.fromEntries(ids.map((v) => [v, punto(data, escenario, c.codigo, v, i)?.p50])) }))
  const inds: IndicadorInversion[] = conIndicadores ? indicadoresInversion(reales, data.clima, anios[i]!) : []
  return calcularRiesgo(sumarIndicadores(base, inds), [...data.variables, ...comoVariables(inds)], pesos)
}
const top = (r: ReturnType<typeof calcularRiesgo>, n = 5) => r.filas.filter((f) => f.indice !== null).slice(0, n).map((f) => nombre.get(f.codigo) ?? f.codigo)

const lineas: string[] = []

describe('los cuatro indicadores, simulados antes de entrar a la app', () => {
  it('cada indicador cubre las 52 comunas, con valores distintos, en el primer y el último año', () => {
    for (const i of [0, anios.length - 1]) {
      const inds = indicadoresInversion(reales, data.clima, anios[i]!)
      expect(inds.map((x) => x.id)).toEqual(['sequia_futura', 'escasez_hidrica', 'red_electrica', 'inversion_evaluada'])
      for (const x of inds) {
        expect(x.valores.size).toBe(52)
        expect(new Set(x.valores.values()).size).toBeGreaterThan(1)
      }
      const cobertura = inds.map((x) => `${x.nombre}: ${x.valores.size} comunas, ${new Set(x.valores.values()).size} valores distintos`)
      lineas.push(`- ${anios[i]}: ${cobertura.join('; ')}.`)
    }
  })

  it.each(PERFILES.map((p) => [p.id, p] as const))('perfil %s: todas las comunas tienen índice y como mucho 3 variables pesan', (_id, p) => {
    const pesos: Record<string, number> = { ...p.prioridades }
    const activos = Object.entries(pesos).filter(([, w]) => w > 0).map(([k]) => k)
    expect(activos.length).toBeLessThanOrEqual(3)
    const ult = anios.length - 1
    const [a, s, c] = ANTES[p.id]!
    const antes = { pm25_anual: a, seguridad: s, crecimiento_poblacion: c }
    const r0 = indice(0, true, pesos)
    expect(r0.total).toBe(52)
    expect([...r0.usadas].sort()).toEqual([...activos].sort())
    const filas = [
      [`${anios[0]}, 3 variables (antes)`, top(indice(0, false, antes))],
      [`${anios[0]}, 7 variables`, top(r0)],
      [`${anios[ult]}, 3 variables (antes)`, top(indice(ult, false, antes))],
      [`${anios[ult]}, 7 variables`, top(indice(ult, true, pesos))],
    ] as const
    lineas.push('', `### ${p.titulo}`, '', `Activos: ${activos.map((k) => `${k} ${pesos[k]}`).join(', ')}.`, '', '| Cálculo | Top 5 de menor riesgo |', '|---|---|')
    for (const [k, t] of filas) lineas.push(`| ${k} | ${t.join(', ')} |`)
  })

  afterAll(() => {
    const doc = [
      '# Simulación: los 4 indicadores dentro del índice',
      '',
      `Generado con \`npm run evaluar -- simular-indicadores\` (viz/scripts/simular-indicadores.eval.ts) el ${new Date().toISOString().slice(0, 10)}. Sin llamadas al modelo.`,
      'Compara, por perfil, el top 5 con las 3 variables simuladas (pesos aprobados antes) contra el índice de 7 variables con 3 activas, en el primer y el último año.',
      'Sequía futura cambia por año (ARClim, ssp245); escasez hídrica, red eléctrica e inversión evaluada son datos fijos.',
      '',
      '## Cobertura',
      '',
      ...lineas,
      '',
    ]
    writeFileSync(resolve(__dirname, '../../docs/simulacion-indicadores.md'), doc.join('\n'))
  })
})
