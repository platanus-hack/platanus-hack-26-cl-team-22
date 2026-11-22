/**
 * «¿Qué pasaría si…?» del agua: décadas posibles de caudal sorteadas a partir de los años medidos.
 *
 * Método: remuestreo por bloques. Cada década simulada se arma pegando tramos de años reales seguidos
 * (bloques de tres), tomados del período que define el escenario. Los bloques conservan lo que un sorteo año
 * por año perdería: que a un año seco suele seguirle otro. El mismo año real se usa para todas las estaciones
 * de una década, así un año seco lo es en toda la cuenca, como en los datos.
 *
 * No es un modelo climático: supone que la próxima década se parece al período elegido. Lo que entrega es la
 * distribución de lo que ese supuesto implica, no un pronóstico.
 */
import { CORTE_CRITICO, type Agua, type Estacion } from './agua'
import { crearPrng } from './prng'

export type EscenarioAgua = 'megasequia' | 'registro' | 'normal'

export const ESCENARIOS_AGUA: readonly { id: EscenarioAgua; titulo: string; detalle: string }[] = [
  { id: 'megasequia', titulo: 'Sigue la megasequía', detalle: 'La próxima década se parece a 2010–2017.' },
  { id: 'registro', titulo: 'Todo el registro', detalle: 'Años secos y lluviosos como entre 1980 y 2017.' },
  { id: 'normal', titulo: 'Vuelve lo normal', detalle: 'La próxima década se parece a 1980–2009.' },
]

export const REPLICAS_AGUA = 500
const BLOQUE = 3

export interface Decadas {
  escenario: EscenarioAgua
  replicas: number
  /** años por década */
  largo: number
  /** índice del año real (de agua.anios) sorteado para cada réplica y año: réplica * largo + año */
  sorteo: Int16Array
}

/** Índices de `anios` que forman el período de cada escenario. */
export function periodoDe(agua: Pick<Agua, 'anios' | 'base' | 'sequia'>, escenario: EscenarioAgua): number[] {
  const [desde, hasta] = escenario === 'megasequia' ? agua.sequia : escenario === 'normal' ? agua.base : [agua.anios[0]!, agua.anios[agua.anios.length - 1]!]
  const out: number[] = []
  agua.anios.forEach((a, i) => {
    if (a >= desde && a <= hasta) out.push(i)
  })
  return out
}

/** Sortea las décadas de un escenario. Con la misma semilla da siempre lo mismo. */
export function sortearDecadas(agua: Pick<Agua, 'anios' | 'base' | 'sequia'>, escenario: EscenarioAgua, largo: number, replicas = REPLICAS_AGUA, semilla = 2026): Decadas {
  const periodo = periodoDe(agua, escenario)
  const sorteo = new Int16Array(replicas * largo)
  if (periodo.length === 0) return { escenario, replicas, largo, sorteo: sorteo.fill(-1) }
  const prng = crearPrng(semilla + escenario.length * 7919)
  const bloque = Math.min(BLOQUE, periodo.length)
  for (let r = 0; r < replicas; r++) {
    let t = 0
    while (t < largo) {
      const inicio = Math.floor(prng.uniform() * (periodo.length - bloque + 1))
      for (let k = 0; k < bloque && t < largo; k++, t++) sorteo[r * largo + t] = periodo[inicio + k]!
    }
  }
  return { escenario, replicas, largo, sorteo }
}

/** Caudal sobre lo normal de una estación en un año real; si ese año no tiene dato, el promedio del período. */
function fraccionesDe(e: Estacion, periodo: readonly number[]): (i: number) => number {
  const normal = e.base ?? e.medio
  const validos = periodo.map((i) => e.anual[i]).filter((v): v is number => v !== null && v !== undefined)
  const respaldo = normal > 0 && validos.length > 0 ? validos.reduce((a, b) => a + b, 0) / validos.length / normal : 1
  return (i) => {
    const v = i >= 0 ? e.anual[i] : null
    return v === null || v === undefined || normal <= 0 ? respaldo : v / normal
  }
}

export interface ResumenSim {
  /** caudal sobre lo normal por año de la década: percentiles entre las réplicas */
  p10: number[]
  p50: number[]
  p90: number[]
  /** fracción de las réplicas con caudal crítico en cada año */
  probCritico: number[]
  /** años en caudal crítico por década, en promedio */
  aniosCriticos: number
  /** fracción de las décadas con al menos tres años críticos seguidos */
  racha3: number
}

const percentil = (ordenados: Float64Array, q: number): number => {
  const pos = (ordenados.length - 1) * q
  const a = Math.floor(pos)
  const b = Math.min(ordenados.length - 1, a + 1)
  return ordenados[a]! + (ordenados[b]! - ordenados[a]!) * (pos - a)
}

/** Lo que las décadas sorteadas dicen de una estación. */
export function resumirSim(agua: Pick<Agua, 'anios' | 'base' | 'sequia'>, e: Estacion, d: Decadas): ResumenSim {
  const f = fraccionesDe(e, periodoDe(agua, d.escenario))
  const p10: number[] = []
  const p50: number[] = []
  const p90: number[] = []
  const probCritico: number[] = []
  const columna = new Float64Array(d.replicas)
  let criticos = 0
  for (let t = 0; t < d.largo; t++) {
    let n = 0
    for (let r = 0; r < d.replicas; r++) {
      const v = f(d.sorteo[r * d.largo + t]!)
      columna[r] = v
      if (v < CORTE_CRITICO) n++
    }
    criticos += n
    probCritico.push(n / d.replicas)
    const orden = Float64Array.from(columna).sort()
    p10.push(percentil(orden, 0.1))
    p50.push(percentil(orden, 0.5))
    p90.push(percentil(orden, 0.9))
  }
  let conRacha = 0
  for (let r = 0; r < d.replicas; r++) {
    let racha = 0
    let maxima = 0
    for (let t = 0; t < d.largo; t++) {
      racha = f(d.sorteo[r * d.largo + t]!) < CORTE_CRITICO ? racha + 1 : 0
      if (racha > maxima) maxima = racha
    }
    if (maxima >= 3) conRacha++
  }
  return { p10, p50, p90, probCritico, aniosCriticos: criticos / d.replicas, racha3: conRacha / d.replicas }
}

/** Caudal sobre lo normal de una estación en cada año de una década concreta (una réplica). */
export function decadaDe(agua: Pick<Agua, 'anios' | 'base' | 'sequia'>, e: Estacion, d: Decadas, replica: number): number[] {
  const f = fraccionesDe(e, periodoDe(agua, d.escenario))
  const r = ((replica % d.replicas) + d.replicas) % d.replicas
  return Array.from({ length: d.largo }, (_, t) => f(d.sorteo[r * d.largo + t]!))
}
