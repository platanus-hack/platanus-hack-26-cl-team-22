import { fmt } from '../lib/format'
import type { Banda } from '../lib/types'

interface Props {
  anios: number[]
  serie: Banda
  /** línea de comparación (mediana del escenario base) */
  comparacion?: number[]
  idxAnio: number
  unidad: string
}

const W = 320
const H = 190
const M = { l: 34, r: 18, t: 10, b: 24 }

function escalaNice(lo: number, hi: number): { min: number; max: number; ticks: number[] } {
  const span = hi - lo || 1
  const paso = Math.pow(10, Math.floor(Math.log10(span / 3)))
  const m = [1, 2, 5, 10].find((k) => span / (k * paso) <= 4) ?? 10
  const step = m * paso
  const min = Math.floor(lo / step) * step
  const max = Math.ceil(hi / step) * step
  const ticks: number[] = []
  for (let v = min; v <= max + step / 2; v += step) ticks.push(v)
  return { min, max, ticks }
}

/** Gráfico SVG dibujado a mano: banda p10 a p90 siempre visible, mediana y, si hay, comparación. */
export function GraficoLinea({ anios, serie, comparacion, idxAnio, unidad }: Props) {
  const todos = [...serie.p10, ...serie.p90, ...(comparacion ?? [])]
  const { min, max, ticks } = escalaNice(Math.min(...todos), Math.max(...todos))
  const n = anios.length
  const x = (i: number) => M.l + (n === 1 ? 0.5 : i / (n - 1)) * (W - M.l - M.r)
  const y = (v: number) => M.t + (1 - (v - min) / (max - min || 1)) * (H - M.t - M.b)
  const linea = (vals: number[]) => vals.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const banda =
    serie.p90.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ') +
    ' ' +
    [...serie.p10]
      .map((v, i) => [v, i] as const)
      .reverse()
      .map(([v, i]) => `L${x(i).toFixed(1)},${y(v).toFixed(1)}`)
      .join(' ') +
    ' Z'
  const paso = Math.max(1, Math.ceil(n / 6))
  const p50 = serie.p50[idxAnio]

  return (
    <svg
      className="grafico"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Proyección de ${anios[0]} a ${anios[n - 1]} con banda p10 a p90, en ${unidad}`}
    >
      {ticks.map((t) => (
        <g key={t}>
          <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="var(--regla)" strokeWidth="1" />
          <text x={M.l - 5} y={y(t) + 3} textAnchor="end">
            {fmt(t, 0)}
          </text>
        </g>
      ))}
      {anios.map((a, i) =>
        i % paso === 0 || i === n - 1 ? (
          <text key={a} x={x(i)} y={H - 8} textAnchor="middle">
            {a}
          </text>
        ) : null,
      )}
      <path d={banda} fill="var(--banda)" stroke="var(--banda-borde)" strokeWidth="0.75" opacity="0.9" />
      {comparacion && (
        <path d={linea(comparacion)} fill="none" stroke="var(--tinta-3)" strokeWidth="1.4" strokeDasharray="4 3" />
      )}
      <path d={linea(serie.p50)} fill="none" stroke="var(--tinta)" strokeWidth="1.8" />
      <line x1={x(idxAnio)} x2={x(idxAnio)} y1={M.t} y2={H - M.b} stroke="var(--acento)" strokeWidth="1" />
      {p50 !== undefined && <circle cx={x(idxAnio)} cy={y(p50)} r="3.5" fill="var(--acento)" />}
    </svg>
  )
}
