import { fmtPct, safeUrl } from '../lib/format'
import type { Comuna, Escenario, Politica } from '../lib/types'

interface Props {
  politicas: Politica[]
  comunas: Comuna[]
  activas: ReadonlySet<string>
  escenario: Escenario
  calculada: boolean
  onAlternar: (id: string) => void
}

const NIVELES: Record<string, string> = { regional: 'Regional', comunal: 'Comunal', proyecto: 'Proyecto' }

function alcance(p: Politica, comunas: Comuna[]): string {
  if (p.comunas === 'todas') return 'Todas las comunas'
  const nombres = p.comunas.map((c) => comunas.find((x) => x.codigo === c)?.nombre ?? c)
  return nombres.length <= 3 ? nombres.join(', ') : `${nombres.length} comunas`
}

/**
 * Columna izquierda: solo la palanca de la simulación y la línea del escenario mostrado.
 * Si hay muchas políticas, solo la lista interior se desplaza; el título y el escenario quedan fijos.
 */
export function PanelPoliticas({ politicas, comunas, activas, escenario, calculada, onAlternar }: Props) {
  return (
    <section className="seccion panel-politicas" aria-labelledby="h-politicas">
      <div className="politicas-cab">
        <h2 id="h-politicas" className="caps">
          Políticas
        </h2>
        <p className="nota">Enciende o apaga cada política para ver qué pasa si se cumple o no.</p>
      </div>
      <div className="politicas-lista">
        {politicas.map((p) => {
          const on = activas.has(p.id)
          const c = p.credibilidad
          const url = safeUrl(p.url)
          return (
            <div className="politica" key={p.id}>
              <div className="politica-cab">
                <span className="politica-nombre" id={`pol-${p.id}`}>
                  {url ? (
                    <a href={url} target="_blank" rel="noopener noreferrer">
                      {p.nombre}
                    </a>
                  ) : (
                    p.nombre
                  )}
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={on}
                  aria-labelledby={`pol-${p.id}`}
                  className="interruptor"
                  onClick={() => onAlternar(p.id)}
                />
              </div>
              <div className="politica-meta caps">
                <span>{NIVELES[p.nivel] ?? p.nivel}</span>
                <span>·</span>
                <span>{alcance(p, comunas)}</span>
              </div>
              <div
                className="credibilidad"
                role="img"
                aria-label={`Credibilidad ${fmtPct(c.media)}, entre ${fmtPct(c.p10)} y ${fmtPct(c.p90)}`}
              >
                <div className="pista" />
                <div className="rango" style={{ left: `${c.p10 * 100}%`, width: `${Math.max(0, c.p90 - c.p10) * 100}%` }} />
                <div className="media" style={{ left: `${c.media * 100}%` }} />
              </div>
              <div className="credibilidad-txt num">
                Credibilidad {fmtPct(c.media)} ({fmtPct(c.p10)}&ndash;{fmtPct(c.p90)})
              </div>
            </div>
          )
        })}
      </div>
      <div className="politicas-pie">
        <div className="escenario-actual">
          Escenario mostrado: <b>{escenario.nombre}</b>
        </div>
        {!calculada && (
          <p className="aviso-escenario" role="status">
            Esta combinación no está calculada. El mapa sigue mostrando el último escenario válido.
          </p>
        )}
      </div>
    </section>
  )
}
