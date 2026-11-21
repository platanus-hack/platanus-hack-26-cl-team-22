import type { Estado, Veredicto } from './estado'
import { fmt } from './format'
import type { Variable } from './types'

/**
 * Índice de riesgo: una sola dimensión a partir de varias variables.
 *
 * Unidad: posición entre las comunas de la región, de 0 a 100. En cada variable, el riesgo de una comuna
 * es el porcentaje de las otras comunas que están mejor que ella (0 = la mejor, 100 = la peor).
 * El índice general es el promedio de esos riesgos, ponderado por la prioridad de cada variable.
 * Se usa la posición y no el valor porque las variables tienen unidades distintas y comunas muy alejadas
 * del resto (San Pedro en aire, Providencia en delitos) aplastarían cualquier escala lineal.
 */

export interface FilaValores {
  codigo: string
  valores: Record<string, number | undefined>
}

export interface RiesgoComuna {
  codigo: string
  /** índice general, 0 a 100; null si la comuna no tiene dato en ninguna variable con prioridad */
  indice: number | null
  /** riesgo por variable, 0 a 100 */
  partes: Record<string, number>
  /** 1 = la de menor riesgo; null si no tiene índice */
  puesto: number | null
}

export interface Riesgo {
  /** de menor a mayor riesgo; las comunas sin índice van al final */
  filas: RiesgoComuna[]
  porCodigo: ReadonlyMap<string, RiesgoComuna>
  /** variables con prioridad mayor que cero y dato en alguna comuna */
  usadas: string[]
  /** comunas con índice */
  total: number
}

const esNum = (v: number | undefined): v is number => typeof v === 'number' && Number.isFinite(v)

/** Riesgo de cada comuna en una variable: porcentaje de las otras comunas que están mejor. */
export function riesgoPorPosicion(valores: ReadonlyMap<string, number>, mejor: Variable['mejor']): Map<string, number> {
  const out = new Map<string, number>()
  const n = valores.size
  for (const [codigo, v] of valores) {
    if (n < 2) {
      out.set(codigo, 50)
      continue
    }
    let mejores = 0
    for (const x of valores.values()) if (mejor === 'menor' ? x < v : x > v) mejores++
    out.set(codigo, (mejores / (n - 1)) * 100)
  }
  return out
}

export function calcularRiesgo(filas: readonly FilaValores[], variables: readonly Variable[], pesos: Readonly<Record<string, number>>): Riesgo {
  const partesPorVar = new Map<string, Map<string, number>>()
  for (const v of variables) {
    const vals = new Map<string, number>()
    for (const f of filas) {
      const x = f.valores[v.id]
      if (esNum(x)) vals.set(f.codigo, x)
    }
    if (vals.size > 0) partesPorVar.set(v.id, riesgoPorPosicion(vals, v.mejor))
  }
  const usadas = [...partesPorVar.keys()].filter((id) => (pesos[id] ?? 0) > 0)

  const out: RiesgoComuna[] = filas.map((f) => {
    const partes: Record<string, number> = {}
    let suma = 0
    let wTot = 0
    for (const [id, m] of partesPorVar) {
      const r = m.get(f.codigo)
      if (r === undefined) continue
      partes[id] = r
      const w = pesos[id] ?? 0
      if (w > 0) {
        suma += w * r
        wTot += w
      }
    }
    return { codigo: f.codigo, indice: wTot > 0 ? suma / wTot : null, partes, puesto: null }
  })
  out.sort((a, b) => {
    if (a.indice === null && b.indice === null) return a.codigo.localeCompare(b.codigo)
    if (a.indice === null) return 1
    if (b.indice === null) return -1
    return a.indice - b.indice || a.codigo.localeCompare(b.codigo)
  })
  let total = 0
  out.forEach((f, i) => {
    if (f.indice !== null) {
      f.puesto = i + 1
      total++
    }
  })
  return { filas: out, porCodigo: new Map(out.map((f) => [f.codigo, f])), usadas, total }
}

export type NivelRiesgo = 'bajo' | 'medio' | 'alto'

/** Tercios de la escala: hasta 33 bajo, hasta 66 medio, más de 66 alto. */
export function nivelRiesgo(r: number): NivelRiesgo {
  return r <= 100 / 3 ? 'bajo' : r <= 200 / 3 ? 'medio' : 'alto'
}

export const TEXTO_RIESGO: Record<NivelRiesgo, string> = { bajo: 'Riesgo bajo', medio: 'Riesgo medio', alto: 'Riesgo alto' }

/** Color del sello que comparte con el veredicto de la norma: alto = rojo, medio = amarillo, bajo = verde. */
export const ESTADO_DE_RIESGO: Record<NivelRiesgo, Estado> = { bajo: 'cumple', medio: 'limite', alto: 'riesgo' }

/** Cortes del mapa: seis papeles, dos por cada tercio del veredicto. */
export const CORTES_RIESGO: readonly number[] = [100 / 6, 100 / 3, 50, 200 / 3, 500 / 6]

/** "peor que el 85 % de las comunas" o "mejor que el 70 % de las comunas". */
export function textoPosicion(r: number): string {
  const p = Math.round(r)
  if (p >= 100) return 'la peor de la región'
  if (p <= 0) return 'la mejor de la región'
  return p >= 50 ? `peor que el ${p} % de las comunas` : `mejor que el ${100 - p} % de las comunas`
}

/** Prioridad de 1 a 10 a partir de un peso de 0 a 1 (los perfiles del archivo vienen así). */
export function aPrioridad(peso: number): number {
  return Math.max(0, Math.min(10, Math.round(peso * 10)))
}

/** Decimales con que se muestra un valor: los números grandes van sin decimales. */
export function decimales(v: number): number {
  return Math.abs(v) >= 100 ? 0 : 1
}

/** Veredicto del índice general: nivel, puesto y hacia dónde va al final de la proyección. */
export function veredictoGeneral(r: RiesgoComuna, total: number, fin?: { indice: number | null; anio: number }): Veredicto | null {
  if (r.indice === null) return null
  const n = nivelRiesgo(r.indice)
  let futuro: string | null = null
  if (fin && fin.indice !== null) {
    const d = Math.round(fin.indice) - Math.round(r.indice)
    const nf = nivelRiesgo(fin.indice)
    const cambio = nf !== n ? ` y pasa a ${TEXTO_RIESGO[nf].toLowerCase()}` : ''
    futuro = d === 0 ? `En ${fin.anio} sigue igual` : `En ${fin.anio} ${d > 0 ? 'sube' : 'baja'} a ${fmt(fin.indice, 0)}${cambio}`
  }
  return { estado: ESTADO_DE_RIESGO[n], titulo: TEXTO_RIESGO[n], razon: r.puesto !== null ? `puesto ${r.puesto} de ${total}` : '', futuro }
}

/**
 * Veredicto de una variable sin norma: su posición entre las comunas y el cambio de su valor
 * desde el año elegido hasta el último.
 */
export function veredictoVariable(
  parte: number,
  p50: readonly number[],
  anios: readonly number[],
  idx: number,
  variable: Pick<Variable, 'mejor' | 'unidad'>,
): Veredicto {
  const n = nivelRiesgo(parte)
  const ult = p50.length - 1
  const v = p50[idx]
  let futuro: string | null = null
  if (v !== undefined && idx < ult && anios.length === p50.length) {
    const fin = p50[ult]!
    const d = fin - v
    // menos de un 3 % (o medio punto) cabe de sobra en la banda: no se anuncia como cambio
    const umbral = Math.max(0.5, Math.abs(v) * 0.03)
    const u = variable.unidad === '%' ? ' %' : ''
    const a = `${fmt(fin, decimales(fin))}${u} en ${anios[ult]}`
    if (Math.abs(d) < umbral) futuro = `No cambia: ${a}`
    else futuro = `${(variable.mejor === 'menor' ? d < 0 : d > 0) ? 'Mejora' : 'Empeora'}: ${a}`
  }
  return { estado: ESTADO_DE_RIESGO[n], titulo: TEXTO_RIESGO[n], razon: textoPosicion(parte), futuro }
}
