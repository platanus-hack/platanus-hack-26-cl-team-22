import { frecuenciaSaturacion, type Evento, type OpcionesAbm, type ParametrosAbm } from '../lib/mudanzasAbm'
import { fmt, fmtSigned } from '../lib/format'
import { REPLICAS_ABM, type SimulacionAbm } from '../lib/useSimulacionAbm'
import { GraficoBanda } from './GraficoBanda'

/**
 * View 5, "Las mudanzas": the agent-based moves simulation (docs/modelo-mudanzas-abm.md).
 * The map paints housing occupancy per comuna; this sheet sets the rules and events and reads
 * what emerges over the runs: the region's band, which comunas saturate and the spilled demand.
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
    texto: 'Ola migratoria',
    detalle: 'Llegadas desde el extranjero ×3 entre 2026 y 2028',
    crear: () => [{ tipo: 'ola_migratoria', desde: DESDE, anios: 3, m: 3 }],
  },
  {
    id: 'congelar',
    texto: 'Congelar permisos',
    detalle: 'Ninguna vivienda nueva desde 2026',
    crear: (_, n) => Array.from({ length: n }, (_, i) => ({ tipo: 'densificar' as const, comuna: i, desde: DESDE, m: 0 })),
  },
  {
    id: 'densificar',
    texto: 'Densificar la comuna elegida',
    detalle: 'Permisos ×3 desde 2026 en la comuna marcada en el mapa',
    crear: (s) => (s >= 0 ? [{ tipo: 'densificar', comuna: s, desde: DESDE, m: 3 }] : []),
    necesitaComuna: true,
  },
  {
    id: 'crisis',
    texto: 'Crisis',
    detalle: 'Mudanzas y llegadas ×2 en 2027',
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
}

export function VistaMudanzas({ datos, resultado, calculando, opciones, onOpciones, anio, seleccionada }: Props) {
  const activos = new Set(opciones.activos ?? [])
  const t = Math.max(0, datos.anios.indexOf(anio))
  const nombre = (i: number) => datos.comunas[i]?.nombre ?? '—'

  const alternar = (ev: DefEvento) => {
    const sig = new Set(activos)
    if (sig.has(ev.id)) sig.delete(ev.id)
    else sig.add(ev.id)
    const eventos = EVENTOS.filter((e) => sig.has(e.id)).flatMap((e) => e.crear(seleccionada, datos.comunas.length))
    onOpciones({ ...opciones, eventos, activos: [...sig] })
  }

  const corridas = resultado?.corridas ?? []
  const saturadas = frecuenciaSaturacion(corridas, t)
  const mediana = (xs: number[]) => (xs.length === 0 ? 0 : xs.slice().sort((a, b) => a - b)[Math.floor(xs.length / 2)]!)
  const tamano = opciones.tamanoGrupo ?? 250
  const hasta = (xs: number[]) => xs.slice(0, t).reduce((a, b) => a + b, 0)
  const derrames = mediana(corridas.map((c) => hasta(c.derrames))) * tamano
  const sinLugar = mediana(corridas.map((c) => hasta(c.noAtendida))) * tamano
  const total = resultado?.total
  const millones = (xs: number[]) => xs.map((v) => v / 1e6)

  return (
    <div className="v-prueba">
      <p className="v-escenario">
        Si la vivienda se llena y cada grupo llega a donde llegaron los suyos, ¿qué comunas se saturan primero y hacia dónde se derrama la gente? El
        mapa muestra la ocupación de la vivienda de cada comuna. Cada una de las {REPLICAS_ABM} corridas es distinta: lo que se ve es lo que
        emerge de las reglas, no un número fijo.
      </p>

      <section className="bloque" aria-labelledby="h-reglas">
        <h3 id="h-reglas">Quienes llegan del extranjero</h3>
        <div role="radiogroup" aria-labelledby="h-reglas" style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {(
            [
              ['redes', 'Siguen a su comunidad'],
              ['fijo', 'Repiten la geografía medida'],
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
        <p className="prueba-frase">
          «Siguen a su comunidad»: cada llegada elige comuna con peso (stock + 1)^{fmt(datos.phi ?? 1, 2)}, así que cada una hace más atractiva su
          comuna para la siguiente. Ajustado con 2012–2017 y probado con 2019–2024.
        </p>
      </section>

      <section className="bloque" aria-labelledby="h-eventos">
        <h3 id="h-eventos">Eventos</h3>
        <ul style={{ listStyle: 'none', padding: 0, display: 'grid', gap: '0.35rem' }}>
          {EVENTOS.map((ev) => (
            <li key={ev.id}>
              <button
                type="button"
                aria-pressed={activos.has(ev.id)}
                className="pestana-mapa"
                disabled={ev.necesitaComuna && seleccionada < 0}
                onClick={() => alternar(ev)}
              >
                {ev.texto}
              </button>{' '}
              <span className="prueba-frase">
                {ev.detalle}
                {ev.necesitaComuna && (seleccionada >= 0 ? `: ${nombre(seleccionada)}` : ' (elige una en el mapa)')}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="bloque" aria-labelledby="h-region" aria-busy={calculando}>
        <h3 id="h-region">Región Metropolitana en {datos.anios[t]}</h3>
        {!total ? (
          <p className="prueba-frase">Simulando…</p>
        ) : (
          <>
            <p className="prueba-frase">
              <b>{fmt(total.p50[t]! / 1e6, 2)} millones</b> (entre {fmt(total.p10[t]! / 1e6, 2)} y {fmt(total.p90[t]! / 1e6, 2)} en el 80 % de las
              corridas), {fmtSigned(((total.p50[t]! - total.p50[0]!) / total.p50[0]!) * 100, 1)} % desde {datos.anios[0]}.
              {calculando && ' Recalculando…'}
            </p>
            <GraficoBanda
              anios={datos.anios}
              serie={{ p10: millones(total.p10), p50: millones(total.p50), p90: millones(total.p90) }}
              idxAnio={t}
              unidad="millones de personas"
              nivelBanda={null}
            />
          </>
        )}
      </section>

      {total && (
        <section className="bloque" aria-labelledby="h-saturan">
          <h3 id="h-saturan">Qué se satura hasta {datos.anios[t]}</h3>
          <p className="prueba-frase">
            {saturadas.length === 0 ? 'Ninguna comuna se llena todavía.' : `${saturadas.length} comunas se llenan en al menos una corrida.`} Personas
            que no cupieron en su primera opción y se fueron a otra: <b>{fmt(derrames, 0)}</b>. Sin lugar en ninguna comuna: <b>{fmt(sinLugar, 0)}</b>{' '}
            (medianas).
          </p>
          <ul className="barras">
            {saturadas.slice(0, 8).map((s) => (
              <li key={s.comuna}>
                <span className="barra-txt">{nombre(s.comuna)}</span>
                <span className="barra-pista">
                  <span className="barra barra-tinta" style={{ width: `${(s.corridas / corridas.length) * 100}%` }} />
                </span>
                <span className="barra-num">
                  {s.corridas} de {corridas.length}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="bloque" aria-labelledby="h-supuestos">
        <h3 id="h-supuestos">Supuestos</h3>
        <p className="aviso aviso-honesto">
          Grupos de {tamano} personas. Capacidad: viviendas del censo 2024 por personas por vivienda ocupada; crece con los permisos del MINVU (media
          2015–2024). Las mudanzas internas repiten los destinos de 2012–2017. El aire no cambia a dónde se muda la gente. Detalle en
          docs/modelo-mudanzas-abm.md.
        </p>
      </section>
    </div>
  )
}
