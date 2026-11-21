import type { Variable } from './types'

export interface FilaValores {
  codigo: string
  valores: Record<string, number | undefined>
}

export interface FilaRanking {
  codigo: string
  /** 0 a 100, mayor es mejor para el hogar; null si la comuna no tiene ninguna variable usada */
  puntaje: number | null
}

export interface Ranking {
  filas: FilaRanking[]
  /** variables con peso > 0 y datos en al menos una comuna */
  usadas: string[]
  /** variables con peso > 0 pero sin ningún dato: se ignoran */
  ignoradas: string[]
}

const esNum = (v: number | undefined): v is number => typeof v === 'number' && Number.isFinite(v)

/**
 * Puntaje = suma ponderada de cada variable normalizada entre comunas (0 a 1),
 * invertida cuando menor es mejor. Se divide por la suma de pesos realmente usados
 * en esa comuna, de modo que las variables sin dato no castigan a nadie.
 */
export function rankear(filas: readonly FilaValores[], variables: readonly Variable[], pesos: Readonly<Record<string, number>>): Ranking {
  const usadas: string[] = []
  const ignoradas: string[] = []
  const rango = new Map<string, [number, number]>()
  const mejor = new Map(variables.map((v) => [v.id, v.mejor]))

  for (const [id, w] of Object.entries(pesos)) {
    if (!(w > 0)) continue
    const vals = filas.map((f) => f.valores[id]).filter(esNum)
    if (vals.length === 0 || !mejor.has(id)) {
      ignoradas.push(id)
      continue
    }
    usadas.push(id)
    rango.set(id, [Math.min(...vals), Math.max(...vals)])
  }

  const out: FilaRanking[] = filas.map((f) => {
    let suma = 0
    let wTot = 0
    for (const id of usadas) {
      const x = f.valores[id]
      if (!esNum(x)) continue
      const [lo, hi] = rango.get(id)!
      let n = hi === lo ? 0.5 : (x - lo) / (hi - lo)
      if (mejor.get(id) === 'menor') n = 1 - n
      const w = pesos[id] ?? 0
      suma += w * n
      wTot += w
    }
    return { codigo: f.codigo, puntaje: wTot > 0 ? (suma / wTot) * 100 : null }
  })

  out.sort((a, b) => {
    if (a.puntaje === null && b.puntaje === null) return a.codigo.localeCompare(b.codigo)
    if (a.puntaje === null) return 1
    if (b.puntaje === null) return -1
    return b.puntaje - a.puntaje || a.codigo.localeCompare(b.codigo)
  })
  return { filas: out, usadas, ignoradas }
}
