import { useMemo } from 'react'
import { punto, serie } from '../lib/data'
import { calcularHallazgos } from '../lib/findings'
import { fmt, fmtBanda, fmtPct, fmtSigned } from '../lib/format'
import type { ResumenOrigen } from '../lib/origen'
import type { Comuna, Escenario, Politica, Simulacion, Variable } from '../lib/types'
import { GraficoLinea } from './GraficoLinea'

interface Props {
  data: Simulacion
  comuna: Comuna
  variable: Variable
  escenario: Escenario
  base: Escenario | undefined
  idxAnio: number
  /** resumen del origen del aire de esta comuna; null si el archivo no trae el dato */
  origen: ResumenOrigen | null
  onCerrar: () => void
}

export function FichaComuna({ data, comuna, variable, escenario, base, idxAnio, origen, onCerrar }: Props) {
  const s = serie(data, escenario.id, comuna.codigo, variable.id)
  const esBase = !base || base.id === escenario.id
  const sBase = base && !esBase ? serie(data, base.id, comuna.codigo, variable.id) : undefined
  const aportes = data.aportes?.[escenario.id]?.[comuna.codigo]?.[variable.id]
  const anios = data.meta.anios

  const hallazgos = useMemo(
    () =>
      s
        ? calcularHallazgos({
            variable,
            anios,
            serie: s,
            escenarioNombre: escenario.nombre,
            esBase,
            base: sBase && base ? { nombre: base.nombre, serie: sBase } : undefined,
            aportes,
            politicas: data.politicas,
          })
        : [],
    [s, variable, anios, escenario, esBase, sBase, base, aportes, data.politicas],
  )

  const p = punto(data, escenario.id, comuna.codigo, variable.id, idxAnio)
  const baseObs = comuna.base[variable.id]
  const nombreComuna = (cod: string) => data.comunas.find((x) => x.codigo === cod)?.nombre ?? cod
  const nombrePol = (id: string): Politica | undefined => data.politicas.find((x) => x.id === id)

  return (
    <article className="ficha" aria-label={`Ficha de ${comuna.nombre}`}>
      <div className="ficha-cab">
        <div>
          <div className="caps">Comuna</div>
          <h2>{comuna.nombre}</h2>
        </div>
        <button type="button" className="boton" onClick={onCerrar}>
          &larr; Volver a la lista
        </button>
      </div>

      {s && p ? (
        <>
          <div className="valor">
            {fmtBanda(p.p50, p.p10, p.p90, variable.unidad)}
            <small>
              {variable.nombre}, {data.meta.anios[idxAnio]}. Mediana y banda p10&ndash;p90.
            </small>
          </div>
          <GraficoLinea anios={anios} serie={s} comparacion={sBase?.p50} idxAnio={idxAnio} unidad={variable.unidad} />
          <div className="leyenda-grafico">
            <span>
              <i style={{ background: 'var(--tinta)', height: 2 }} />
              Mediana
            </span>
            <span>
              <i style={{ background: 'var(--banda)', border: '1px solid var(--banda-borde)' }} />
              Banda p10&ndash;p90
            </span>
            {sBase && (
              <span>
                <i style={{ borderTop: '2px dashed var(--tinta-3)', height: 0 }} />
                Mediana de &laquo;{base?.nombre}&raquo;
              </span>
            )}
          </div>
          {baseObs !== undefined && (
            <p className="nota">
              Medición de partida ({data.meta.anio_base ?? 'año base'}): <span className="num">{fmt(baseObs)} {variable.unidad}</span> (dato observado, no proyectado)
            </p>
          )}

          <ul className="hallazgos">
            {hallazgos.map((h, i) => (
              <li key={i}>{h}</li>
            ))}
          </ul>

          {origen && (
            <section className="origen-aire" aria-labelledby="h-origen">
              <h3 id="h-origen" className="caps">
                De dónde viene su aire
              </h3>
              {origen.propia !== null ? (
                <p className="origen-propia">
                  Emisiones de la propia comuna: <b className="num">{fmtPct(origen.propia)}</b> de su PM2,5.
                </p>
              ) : (
                <p className="origen-propia">Este archivo no separa la parte que viene de la propia comuna.</p>
              )}
              {origen.otros.length > 0 && (
                <ul className="origen-lista">
                  {origen.otros.map((o) => (
                    <li key={o.origen}>
                      <span className="origen-nombre">{nombreComuna(o.origen)}</span>
                      <span className="origen-barra" aria-hidden="true">
                        <i style={{ width: `${Math.min(100, o.fraccion * 100)}%` }} />
                      </span>
                      <span className="num">{fmtPct(o.fraccion)}</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="origen-resto">
                Otras comunas y fondo regional: <span className="num">{fmtPct(origen.resto)}</span>
              </p>
              <p className="nota">
                Participación estimada para &laquo;{escenario.nombre}&raquo;, sin banda de incertidumbre en este archivo; no cambia con el año. Las
                líneas del mapa tienen un ancho proporcional a estas partes.
              </p>
            </section>
          )}

          {aportes && aportes.length > 0 && (
            <div className="aportes">
              <div className="caps" style={{ marginBottom: 4 }}>
                Aporte de cada política al valor final
              </div>
              <table>
                <tbody>
                  {[...aportes]
                    .sort((a, b) => Math.abs(b.delta_p50_final) - Math.abs(a.delta_p50_final))
                    .map((a) => (
                      <tr key={a.politica_id}>
                        <td>{nombrePol(a.politica_id)?.nombre ?? a.politica_id}</td>
                        <td className="num">
                          {fmtSigned(a.delta_p50_final)} {variable.unidad}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
              <p className="nota">Efecto sobre la mediana del último año. La banda de incertidumbre no se reparte por política.</p>
            </div>
          )}
        </>
      ) : (
        <p className="ficha-vacia">Esta comuna no tiene proyección para este escenario y variable.</p>
      )}
    </article>
  )
}
