import { fmt, fmtBanda } from './format'
import type { Aporte, Banda, Politica, Variable } from './types'

export interface EntradaHallazgos {
  variable: Variable
  anios: number[]
  serie: Banda
  escenarioNombre: string
  esBase: boolean
  /** serie del escenario base para la misma comuna, si existe y es otro escenario */
  base?: { nombre: string; serie: Banda }
  aportes?: Aporte[]
  politicas: Politica[]
}

/** Texto de una variación de la mediana, con el sentido (mejora o empeora) según `mejor`. */
function sentido(delta: number, variable: Variable, umbral: number): { verbo: string; juicio: string } {
  if (Math.abs(delta) < umbral) return { verbo: 'casi no cambia', juicio: '' }
  const sube = delta > 0
  const bueno = variable.mejor === 'menor' ? !sube : sube
  return { verbo: sube ? 'sube' : 'baja', juicio: bueno ? ' (mejora)' : ' (empeora)' }
}

/** Hasta tres hallazgos en español llano, calculados solo con los datos recibidos. */
export function calcularHallazgos(e: EntradaHallazgos): string[] {
  const out: string[] = []
  const n = e.anios.length
  const u = e.variable.unidad
  if (n >= 2 && e.serie.p50.length === n) {
    const a0 = e.anios[0]!
    const a1 = e.anios[n - 1]!
    const ini = fmtBanda(e.serie.p50[0]!, e.serie.p10[0]!, e.serie.p90[0]!, '', 1)
    const fin = fmtBanda(e.serie.p50[n - 1]!, e.serie.p10[n - 1]!, e.serie.p90[n - 1]!, '', 1)
    const delta = e.serie.p50[n - 1]! - e.serie.p50[0]!
    const s = sentido(delta, e.variable, Math.max(0.01 * Math.abs(e.serie.p50[0]!), 0.3))
    out.push(
      `Entre ${a0} y ${a1} la mediana ${s.verbo}${s.verbo === 'casi no cambia' ? '' : ` ${fmt(Math.abs(delta))} ${u}`}${s.juicio}: de ${ini} a ${fin} ${u}.`,
    )
  }

  if (e.base && !e.esBase && n >= 1 && e.base.serie.p50.length === n) {
    const i = n - 1
    const d = e.serie.p50[i]! - e.base.serie.p50[i]!
    const solapa = e.serie.p10[i]! <= e.base.serie.p90[i]! && e.base.serie.p10[i]! <= e.serie.p90[i]!
    const s = sentido(d, e.variable, 0.3)
    const nota = solapa ? ' Las bandas se solapan: la diferencia podría no ser real.' : ' Las bandas no se solapan.'
    if (s.verbo === 'casi no cambia') {
      out.push(`En ${e.anios[i]} este escenario queda prácticamente igual que "${e.base.nombre}".${nota}`)
    } else {
      const cmp = d > 0 ? 'más alta' : 'más baja'
      out.push(`En ${e.anios[i]} la mediana es ${fmt(Math.abs(d))} ${u} ${cmp} que en "${e.base.nombre}"${s.juicio}.${nota}`)
    }
  }

  if (e.aportes && e.aportes.length > 0) {
    const top = [...e.aportes].sort((a, b) => Math.abs(b.delta_p50_final) - Math.abs(a.delta_p50_final))[0]!
    if (Math.abs(top.delta_p50_final) > 0) {
      const nombre = e.politicas.find((p) => p.id === top.politica_id)?.nombre ?? top.politica_id
      const s = sentido(top.delta_p50_final, e.variable, 0)
      out.push(
        `La política que más mueve el resultado es "${nombre}": ${s.verbo} ${fmt(Math.abs(top.delta_p50_final))} ${u} la mediana final${s.juicio}.`,
      )
    }
  }
  return out.slice(0, 3)
}
