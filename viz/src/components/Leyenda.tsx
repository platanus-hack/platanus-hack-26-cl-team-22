import { bordes, clase } from '../lib/color'
import { bordesDiferencia, claseDiferencia } from '../lib/diferencia'
import { fmt, fmtSigned } from '../lib/format'
import type { Variable } from '../lib/types'

export interface LeyendaDiferencia {
  max: number
  /** 5 colores; el índice 0 es la mayor mejora */
  paleta: string[]
  baseNombre: string
}

interface Props {
  variable: Variable
  dominio: [number, number]
  rampa: string[]
  diferencia: LeyendaDiferencia | null
}

export function Leyenda({ variable, dominio, rampa, diferencia }: Props) {
  if (diferencia) return <LeyendaDif variable={variable} d={diferencia} />
  const b = bordes(dominio)
  return (
    <div className="leyenda" aria-label="Leyenda del mapa">
      <div className="caps">
        {variable.nombre} · <span style={{ textTransform: 'none' }}>{variable.unidad}</span>
      </div>
      <div className="leyenda-barra">
        {rampa.map((_, i) => {
          const medio = (b[i]! + b[i + 1]!) / 2
          return <span key={i} style={{ background: rampa[clase(medio, dominio, variable.mejor)] }} />
        })}
        <span className="nd" title="Sin dato" />
      </div>
      <div className="leyenda-marcas">
        {b.map((v, i) => (
          <span key={i} style={{ left: `${(i / (b.length - 1)) * 100}%` }}>
            {fmt(v, 0)}
          </span>
        ))}
      </div>
      <div className="leyenda-txt">Mediana p50; la altura es proporcional al valor. Más oscuro, peor. Trama gris: sin dato.</div>
    </div>
  )
}

function LeyendaDif({ variable, d }: { variable: Variable; d: LeyendaDiferencia }) {
  const b = bordesDiferencia(d.max)
  return (
    <div className="leyenda" aria-label="Leyenda del mapa: diferencia">
      <div className="caps">
        Diferencia de mediana · <span style={{ textTransform: 'none' }}>{variable.unidad}</span>
      </div>
      <div className="leyenda-barra">
        {d.paleta.map((color, i) => {
          // el centro de cada tramo, para que el color coincida con claseDiferencia
          const medio = (b[i]! + b[i + 1]!) / 2
          const c = d.paleta[claseDiferencia(medio, d.max, variable.mejor)] ?? color
          return <span key={i} style={{ background: c }} />
        })}
        <span className="nd" title="Sin dato" />
      </div>
      <div className="leyenda-marcas">
        {b.map((v, i) => (
          <span key={i} style={{ left: `${(i / (b.length - 1)) * 100}%` }}>
            {fmtSigned(v, 1)}
          </span>
        ))}
      </div>
      <div className="leyenda-txt">
        Frente a &laquo;{d.baseNombre}&raquo;. Verde azulado: mejora; ladrillo: empeora; papel: sin cambio. La altura es la magnitud de la diferencia.
      </div>
    </div>
  )
}
