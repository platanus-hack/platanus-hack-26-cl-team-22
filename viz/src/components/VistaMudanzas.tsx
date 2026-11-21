import { fmt } from '../lib/format'
import { CORTES_OCUPACION, estadoOcupacion, frecuenciaSaturacion, serieOcupacion, type Evento, type OpcionesAbm, type ParametrosAbm } from '../lib/mudanzasAbm'
import { nivel, papelNivel } from '../lib/niveles'
import { REPLICAS_ABM, type SimulacionAbm } from '../lib/useSimulacionAbm'
import { GraficoBanda } from './GraficoBanda'
import { ClaveGrafico, Rodela } from './Papel'

/**
 * Section "Desarrollo urbano: quién se muda a dónde": the agent-based moves simulation
 * (docs/modelo-mudanzas-abm.md). Same layout as the other detail sections: the chosen comuna's
 * housing occupancy, its band over the years, what-if events, and the three that fill most.
 * How it works and its assumptions stay folded.
 */

const DESDE = 2026

interface DefEvento {
  id: string
  texto: string
  detalle: string
  crear: (seleccionada: number, nComunas: number) => Evento[]
  necesitaComuna?: boolean
}

const EVENTOS: DefEvento[] = [
  {
    id: 'ola',
    texto: 'Llegan 3 veces más extranjeros',
    detalle: 'entre 2026 y 2028',
    crear: () => [{ tipo: 'ola_migratoria', desde: DESDE, anios: 3, m: 3 }],
  },
  {
    id: 'congelar',
    texto: 'No se construye más',
    detalle: 'ningún permiso nuevo desde 2026',
    crear: (_, n) => Array.from({ length: n }, (_, i) => ({ tipo: 'densificar' as const, comuna: i, desde: DESDE, m: 0 })),
  },
  {
    id: 'densificar',
    texto: 'Se construye el triple aquí',
    detalle: 'en la comuna elegida, desde 2026',
    crear: (s) => (s >= 0 ? [{ tipo: 'densificar', comuna: s, desde: DESDE, m: 3 }] : []),
    necesitaComuna: true,
  },
  {
    id: 'crisis',
    texto: 'Un año de crisis',
    detalle: 'el doble de mudanzas y llegadas en 2027',
    crear: () => [{ tipo: 'crisis', desde: 2027, anios: 1, m: 2 }],
  },
]

/** Options of the simulation plus which events the sheet has switched on. */
export type OpcionesMudanzas = OpcionesAbm & { activos?: string[] }

interface Props {
  datos: ParametrosAbm
  resultado: SimulacionAbm | null
  calculando: boolean
  opciones: OpcionesMudanzas
  onOpciones: (o: OpcionesMudanzas) => void
  anio: number
  /** index of the comuna chosen on the map, or −1 */
  seleccionada: number
  onSeleccionar: (codigo: string) => void
}

export function VistaMudanzas({ datos, resultado, calculando, opciones, onOpciones, anio, seleccionada, onSeleccionar }: Props) {
  const activos = new Set(opciones.activos ?? [])
  const t = Math.max(0, datos.anios.indexOf(anio))
  const comuna = seleccionada >= 0 ? datos.comunas[seleccionada] : undefined
  const corridas = resultado?.corridas ?? []
  const saturadas = frecuenciaSaturacion(corridas, t)
  const veces = new Map(saturadas.map((s) => [s.comuna, s.corridas]))

  const alternar = (ev: DefEvento) => {
    const sig = new Set(activos)
    if (sig.has(ev.id)) sig.delete(ev.id)
    else sig.add(ev.id)
    const eventos = EVENTOS.filter((e) => sig.has(e.id)).flatMap((e) => e.crear(seleccionada, datos.comunas.length))
    onOpciones({ ...opciones, eventos, activos: [...sig] })
  }

  const serie = comuna && corridas.length > 0 ? serieOcupacion(corridas, seleccionada) : null
  const p50 = serie?.p50[t]
  const hayDato = p50 !== undefined && Number.isFinite(p50)
  const estado = hayDato ? estadoOcupacion(p50, veces.get(seleccionada) ?? 0, corridas.length) : null
  const txt = hayDato ? `${fmt(p50, 0)} %` : '—'
  const vecesAqui = veces.get(seleccionada) ?? 0
  const activosTexto = EVENTOS.filter((e) => activos.has(e.id)).map((e) => `${e.texto.toLowerCase()}, ${e.detalle}`)

  return (
    <div className="v-riesgo v-mudanzas" aria-busy={calculando}>
      {!comuna ? (
        <p className="v-vacia">Elige una comuna en el mapa.</p>
      ) : !resultado ? (
        <p className="v-vacia">Simulando…</p>
      ) : (
        <>
          <div className="cuenca-fila detalle-fila">
            <Rodela
              nivel={hayDato ? papelNivel(nivel(p50, CORTES_OCUPACION), CORTES_OCUPACION) : null}
              borde={null}
              etiqueta={`${txt} de la vivienda ocupada en ${anio}`}
            >
              <span className="numeral">
                {hayDato ? fmt(p50, 0) : '—'}
                {hayDato && <small>%</small>}
              </span>
            </Rodela>
            <div className="cuenca-lectura">
              <h2 className="detalle-nombre">{comuna.nombre}</h2>
              <p className="detalle-que">Vivienda ocupada · % de la capacidad</p>
              {estado && (
                <div className="veredicto">
                  <p className="veredicto-fila">
                    <b className={`sello sello-${estado.estado}`}>{estado.titulo}</b>
                    <span>
                      {vecesAqui > 0
                        ? `se llena en ${vecesAqui} de ${corridas.length} simulaciones hasta ${anio}`
                        : `no se llena en ninguna de las ${corridas.length} simulaciones hasta ${anio}`}
                    </span>
                  </p>
                </div>
              )}
            </div>
          </div>

          {serie && (
            <section className="tramo" aria-label={`Ocupación de la vivienda en ${comuna.nombre}`}>
              <ClaveGrafico nivelBanda={0} />
              <GraficoBanda anios={datos.anios} serie={serie} idxAnio={t} unidad="% de la capacidad" nivelBanda={0} alto={112} />
            </section>
          )}
        </>
      )}

      <section className="tramo" aria-labelledby="h-que-pasa">
        <h3 id="h-que-pasa">¿Qué pasa si…?</h3>
        <div className="perfiles">
          {EVENTOS.map((ev) => (
            <button
              key={ev.id}
              type="button"
              className="lectura"
              aria-pressed={activos.has(ev.id)}
              disabled={ev.necesitaComuna && !comuna}
              title={ev.necesitaComuna && !comuna ? 'Elige una comuna en el mapa' : ev.detalle}
              onClick={() => alternar(ev)}
            >
              {ev.texto}
            </button>
          ))}
        </div>
        {activosTexto.length > 0 && <p className="nota">{activosTexto.join('; ').replace(/^./, (c) => c.toUpperCase())}.</p>}
      </section>

      {saturadas.length > 0 && (
        <section className="tramo" aria-labelledby="h-se-llenan">
          <h3 id="h-se-llenan">
            Las 3 que más se llenan
            <span className="grafico-clave">hasta {anio}</span>
          </h3>
          <div className="perfiles">
            {saturadas.slice(0, 3).map((s) => (
              <button
                key={s.comuna}
                type="button"
                className="lectura"
                aria-pressed={s.comuna === seleccionada}
                onClick={() => onSeleccionar(datos.comunas[s.comuna]!.codigo)}
              >
                {datos.comunas[s.comuna]!.nombre}
              </button>
            ))}
          </div>
        </section>
      )}

      <details className="limites">
        <summary>Cómo funciona</summary>
        <p>
          Simulamos {REPLICAS_ABM} veces cómo se mueve la gente, en grupos de {opciones.tamanoGrupo ?? 250} personas. Cada comuna recibe a tantas
          personas como caben en sus viviendas del censo 2024, y suma las que autorizan los permisos de edificación. Cuando una se llena,
          quien quería llegar busca otra.
        </p>
        <div className="perfiles" role="radiogroup" aria-label="Quienes llegan del extranjero">
          {(
            [
              ['redes', 'Los extranjeros siguen a su comunidad'],
              ['fijo', 'Los extranjeros repiten lo medido'],
            ] as const
          ).map(([modo, texto]) => (
            <button
              key={modo}
              type="button"
              role="radio"
              aria-checked={opciones.modoExtranjero === modo}
              className="lectura"
              onClick={() => onOpciones({ ...opciones, modoExtranjero: modo })}
            >
              {texto}
            </button>
          ))}
        </div>
        <p>
          Las mudanzas dentro de la región repiten los destinos medidos entre 2012 y 2017. El aire y los precios no cambian a dónde se muda la gente.
          Detalle y pruebas en docs/modelo-mudanzas-abm.md.
        </p>
      </details>
    </div>
  )
}
