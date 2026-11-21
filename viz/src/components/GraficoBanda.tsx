import { fmt } from '../lib/format'
import type { Banda } from '../lib/types'

interface Props {
  anios: number[]
  serie: Banda
  comparacion?: { nombre: string; p50: number[] }
  idxAnio: number
  unidad: string
  /** línea de referencia (p. ej. la norma), solo si viene en los datos */
  referencia?: { valor: number; texto: string }
  nivelBanda: number | null
  /** alto del dibujo en unidades del viewBox (ancho 480) */
  alto?: number
}

const W = 480
const M = { l: 36, r: 12, t: 10, b: 26 }

function escala(lo: number, hi: number): { min: number; max: number; ticks: number[] } {
  const span = hi - lo || 1
  const paso0 = Math.pow(10, Math.floor(Math.log10(span / 3)))
  const m = [1, 2, 5, 10].find((k) => span / (k * paso0) <= 4) ?? 10
  const paso = m * paso0
  const min = Math.floor(lo / paso) * paso
  const max = Math.ceil(hi / paso) * paso
  const ticks: number[] = []
  for (let v = min; v <= max + paso / 2; v += paso) ticks.push(Number(v.toFixed(6)))
  return { min, max, ticks }
}

/** Proyección dibujada a mano: la banda p10–p90 es un papel recortado, la mediana es tinta. */
export function GraficoBanda({ anios, serie, comparacion, idxAnio, unidad, referencia, nivelBanda, alto = 165 }: Props) {
  const H = alto
  const vals = [...serie.p10, ...serie.p90, ...(comparacion?.p50 ?? [])]
  if (referencia) vals.push(referencia.valor)
  const { min, max, ticks } = escala(Math.min(...vals), Math.max(...vals))
  const n = anios.length
  const x = (i: number) => M.l + (n === 1 ? 0.5 : i / (n - 1)) * (W - M.l - M.r)
  const y = (v: number) => M.t + (1 - (v - min) / (max - min || 1)) * (H - M.t - M.b)
  const linea = (vs: number[]) => vs.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')
  const banda =
    serie.p90.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('') +
    [...serie.p10]
      .map((v, i) => [v, i] as const)
      .reverse()
      .map(([v, i]) => `L${x(i).toFixed(1)},${y(v).toFixed(1)}`)
      .join('') +
    'Z'
  const cada = Math.max(1, Math.ceil(n / 6))
  const p50 = serie.p50[idxAnio]

  return (
    <svg className="grafico" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Proyección de ${anios[0]} a ${anios[n - 1]}: mediana y banda p10 a p90, en ${unidad}`}>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} className="g-regla" />
          <text x={M.l - 7} y={y(t) + 4} textAnchor="end" className="g-txt">
            {fmt(t, Number.isInteger(t) ? 0 : 1)}
          </text>
        </g>
      ))}
      {anios.map((a, i) =>
        i % cada === 0 || i === n - 1 ? (
          <text key={a} x={x(i)} y={H - 8} textAnchor={i === n - 1 ? "end" : i === 0 ? "start" : "middle"} className="g-txt">
            {a}
          </text>
        ) : null,
      )}
      <path d={banda} className="alzado-sombra" transform="translate(1 1)" />
      {/* papel claro de la familia del nivel: la tinta de la mediana debe leerse encima */}
      <path d={banda} className={`g-banda ${nivelBanda !== null && nivelBanda >= 2 ? 'nivel-1' : 'nivel-0'}`} />
      {referencia && (
        <g>
          <line x1={M.l} x2={W - M.r} y1={y(referencia.valor)} y2={y(referencia.valor)} className="g-ref" />
          <text x={M.l + 6} y={y(referencia.valor) - 6} textAnchor="start" className="g-txt g-txt-ref">
            {referencia.texto}
          </text>
        </g>
      )}
      {comparacion && <path d={linea(comparacion.p50)} className="g-comp" />}
      <path d={linea(serie.p50)} className="g-mediana" />
      <line x1={x(idxAnio)} x2={x(idxAnio)} y1={M.t} y2={H - M.b} className="g-hoy" />
      {p50 !== undefined && <circle cx={x(idxAnio)} cy={y(p50)} r="5" className="g-punto" />}
    </svg>
  )
}
