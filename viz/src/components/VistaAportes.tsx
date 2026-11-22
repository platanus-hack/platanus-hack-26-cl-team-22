import { useEffect, useMemo, useState } from 'react'
import {
  aportePorEstado,
  filtrarLicitaciones,
  leerLicitaciones,
  leerProyectos,
  montoDe,
  pagina,
  pesosCortos,
  TEXTO_ESTADO_LICITACION,
  type EstadoLicitacion,
  type LicitacionesComuna,
  type OrdenLicitacion,
  type ProyectoSeia,
} from '../lib/aportes'
import { fmt } from '../lib/format'

interface Props {
  /** código de la comuna en los archivos de datos (cinco dígitos); null si no hay comuna elegida */
  codigo: string | null
  nombre: string
}

type Carga<T> = { estado: 'cargando' } | { estado: 'falla' } | { estado: 'listo'; datos: T }

const POR_PAGINA = 4
const leer = async (url: string): Promise<unknown> => {
  const r = await fetch(url, { cache: 'force-cache', credentials: 'omit' })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
/** El archivo de proyectos trae las 52 comunas: se pide una sola vez. */
let proyectosCrudos: Promise<unknown> | null = null

/** Aporte a la credibilidad en puntos de una escala de 0 a 100, con signo. */
const puntos = (aporte: number) => `${aporte > 0 ? '+' : aporte < 0 ? '−' : ''}${fmt(Math.abs(aporte) * 100, 3)} pt`

function Paginas({ actual, paginas, onIr }: { actual: number; paginas: number; onIr: (n: number) => void }) {
  if (paginas < 2) return null
  return (
    <div className="aportes-paginas">
      <button type="button" className="lectura ajustar" disabled={actual === 0} onClick={() => onIr(actual - 1)}>
        Anteriores
      </button>
      <span>
        {actual + 1} de {paginas}
      </span>
      <button type="button" className="lectura ajustar" disabled={actual >= paginas - 1} onClick={() => onIr(actual + 1)}>
        Siguientes
      </button>
    </div>
  )
}

/**
 * Qué hay detrás de dos indicadores de la comuna: sus proyectos SEIA y sus licitaciones, cada uno con su aporte.
 * Se muestra una lista a la vez, paginada, para no llenar la hoja.
 */
export function VistaAportes({ codigo, nombre }: Props) {
  const [lista, setLista] = useState<'proyectos' | 'licitaciones'>('proyectos')
  const [proyectos, setProyectos] = useState<Carga<ProyectoSeia[]>>({ estado: 'cargando' })
  const [lics, setLics] = useState<Carga<LicitacionesComuna>>({ estado: 'cargando' })
  const [pag, setPag] = useState(0)
  const [estado, setEstado] = useState<EstadoLicitacion | null>(null)
  const [orden, setOrden] = useState<OrdenLicitacion>('monto')
  const [abierta, setAbierta] = useState<string | null>(null)

  useEffect(() => {
    if (!codigo) return
    let vivo = true
    setProyectos({ estado: 'cargando' })
    setLics({ estado: 'cargando' })
    setPag(0)
    setAbierta(null)
    proyectosCrudos ??= leer('datos/inversion_proyectos.json')
    proyectosCrudos
      .then((raw) => {
        const p = leerProyectos(raw, codigo)
        if (vivo) setProyectos(p ? { estado: 'listo', datos: p } : { estado: 'falla' })
      })
      .catch(() => {
        proyectosCrudos = null
        if (vivo) setProyectos({ estado: 'falla' })
      })
    // el código viene de nuestro propio mapa; aun así solo se pide si son cinco dígitos
    if (/^\d{5}$/.test(codigo))
      leer(`datos/licitaciones/${codigo}.json`)
        .then((raw) => {
          const l = leerLicitaciones(raw)
          if (vivo) setLics(l ? { estado: 'listo', datos: l } : { estado: 'falla' })
        })
        .catch(() => vivo && setLics({ estado: 'falla' }))
    else setLics({ estado: 'falla' })
    return () => {
      vivo = false
    }
  }, [codigo])

  const filtradas = useMemo(() => (lics.estado === 'listo' ? filtrarLicitaciones(lics.datos.licitaciones, estado, orden) : []), [lics, estado, orden])

  if (!codigo) return <p className="v-vacia">Elige una comuna en el mapa.</p>

  const nProy = proyectos.estado === 'listo' ? proyectos.datos.length : null
  const nLic = lics.estado === 'listo' ? lics.datos.licitaciones.length : null
  const cambiar = (l: 'proyectos' | 'licitaciones') => {
    setLista(l)
    setPag(0)
    setAbierta(null)
  }

  let cuerpo
  if (lista === 'proyectos') {
    if (proyectos.estado === 'cargando') cuerpo = <p className="nota">Buscando los proyectos de {nombre}…</p>
    else if (proyectos.estado === 'falla') cuerpo = <p className="nota nota-sin">No se pudo leer la lista de proyectos SEIA. El resto del análisis sigue igual.</p>
    else {
      const p = pagina(proyectos.datos, pag, POR_PAGINA)
      cuerpo = (
        <>
          <p className="aportes-clave">
            <b>{proyectos.datos.length}</b> proyectos aprobados desde 2015. Cada uno suma <b>+1</b> al indicador «inversión evaluada»; el monto es contexto y no se suma.
          </p>
          <ul className="aportes-lista">
            {p.filas.map((x) => (
              <li key={x.id} className="aporte">
                <div className="aporte-texto">
                  {x.url ? (
                    <a href={x.url} target="_blank" rel="noopener noreferrer">
                      {x.nombre}
                    </a>
                  ) : (
                    <span>{x.nombre}</span>
                  )}
                  <small>{[x.titular, x.tipo, x.fecha.slice(0, 4)].filter(Boolean).join(' · ')}</small>
                </div>
                <span className="aporte-monto">{x.monto === null ? 'sin monto' : `US$ ${fmt(x.monto, x.monto >= 100 ? 0 : 1)} MM`}</span>
                <span className="sello sello-cumple">+1</span>
              </li>
            ))}
          </ul>
          <Paginas actual={p.actual} paginas={p.paginas} onIr={setPag} />
          <p className="nota">Fuente: SEIA (SEA), proyectos aprobados 2015–2026. Un proyecto que nombra varias comunas cuenta una vez en cada una.</p>
        </>
      )
    }
  } else if (lics.estado === 'cargando') cuerpo = <p className="nota">Buscando las licitaciones de {nombre}…</p>
  else if (lics.estado === 'falla') cuerpo = <p className="nota nota-sin">No se pudo leer la lista de licitaciones. El resto del análisis sigue igual.</p>
  else {
    const c = lics.datos
    const p = pagina(filtradas, pag, POR_PAGINA)
    const porEstado = aportePorEstado(c)
    cuerpo = (
      <>
        {c.afectaModelo ? (
          <p className="aportes-clave">
            Credibilidad municipal: <b>{c.credibilidad === null ? 'sin dato' : fmt(c.credibilidad * 100, 1)}</b> de 100. Cada adjudicada la mueve{' '}
            <b>{puntos(porEstado.adjudicada ?? 0)}</b> y cada fallida <b>{puntos(porEstado.fallida ?? 0)}</b>: el modelo solo mira si se adjudicó, no el monto ni el sector.
          </p>
        ) : (
          <p className="aportes-clave aportes-aviso">
            <b>Estas licitaciones son contexto.</b> El modelo solo usa las de las 5 comunas con más delitos; aquí el aporte es 0 porque no entran al modelo, no porque no importen.
          </p>
        )}
        <div className="aportes-filtros" role="group" aria-label="Filtrar licitaciones">
          {([null, 'adjudicada', 'fallida', 'abierta'] as const).map((e) => (
            <button
              key={e ?? 'todas'}
              type="button"
              className="lectura"
              aria-pressed={estado === e}
              onClick={() => {
                setEstado(e)
                setPag(0)
              }}
            >
              {e ? `${TEXTO_ESTADO_LICITACION[e]}s ${c.conteo[e]}` : `Todas ${c.licitaciones.length}`}
            </button>
          ))}
          {c.afectaModelo && (
            <button type="button" className="lectura ajustar" onClick={() => setOrden(orden === 'monto' ? 'aporte' : 'monto')}>
              Orden: {orden === 'monto' ? 'mayor monto' : 'mayor aporte'}
            </button>
          )}
        </div>
        <ul className="aportes-lista">
          {p.filas.map((l) => {
            const id = `${l.codigo}|${l.nombre}`
            const esta = abierta === id
            return (
              <li key={id}>
                <button type="button" className={`aporte aporte-boton${esta ? ' aporte-abierto' : ''}`} aria-expanded={esta} onClick={() => setAbierta(esta ? null : id)}>
                  <span className="aporte-texto">
                    <span>{l.nombre}</span>
                    <small>{[TEXTO_ESTADO_LICITACION[l.estado], l.sector, l.codigo].filter(Boolean).join(' · ')}</small>
                  </span>
                  <span className="aporte-monto">{pesosCortos(montoDe(l), fmt)}</span>
                  <span className={`sello ${l.aporte > 0 ? 'sello-cumple' : l.aporte < 0 ? 'sello-riesgo' : 'sello-sin'}`}>{c.afectaModelo ? puntos(l.aporte) : 'contexto'}</span>
                </button>
                {esta && (
                  <p className="aporte-detalle">
                    {c.afectaModelo && c.credibilidad !== null && l.aporte !== 0
                      ? `Sin esta licitación, la credibilidad de ${nombre} sería ${fmt((c.credibilidad - l.aporte) * 100, 3)} en vez de ${fmt(c.credibilidad * 100, 3)}. `
                      : l.estado === 'abierta'
                        ? 'Aún sin resolver: no entra a la credibilidad. '
                        : 'No entra al modelo en esta comuna. '}
                    Estimado {pesosCortos(l.estimado, fmt)}; adjudicado {pesosCortos(l.adjudicado, fmt)}
                    {l.oferentes !== null ? `; ${fmt(l.oferentes, 0)} oferente${l.oferentes === 1 ? '' : 's'}` : ''}.
                  </p>
                )}
              </li>
            )
          })}
        </ul>
        {filtradas.length === 0 && <p className="nota">Ninguna licitación en ese estado.</p>}
        <Paginas actual={p.actual} paginas={p.paginas} onIr={setPag} />
        <p className="nota">
          Fuente: ChileCompra, {c.anio}.{' '}
          {c.afectaModelo &&
            `Los aportes no suman el total: el modelo pesa como máximo ${c.tope === null ? '40' : fmt(c.tope, 0)} licitaciones efectivas. `}
          No se muestra el efecto sobre los delitos: el de una sola licitación queda por debajo de lo que la simulación distingue.
        </p>
      </>
    )
  }

  return (
    <div className="v-aportes">
      <div className="aportes-listas" role="group" aria-label="Qué lista ver">
        <button type="button" className="lectura" aria-pressed={lista === 'proyectos'} onClick={() => cambiar('proyectos')}>
          Proyectos SEIA{nProy === null ? '' : ` · ${nProy}`}
        </button>
        <button type="button" className="lectura" aria-pressed={lista === 'licitaciones'} onClick={() => cambiar('licitaciones')}>
          Licitaciones 2024{nLic === null ? '' : ` · ${fmt(nLic, 0)}`}
        </button>
        <b className="aportes-comuna">{nombre}</b>
      </div>
      {cuerpo}
    </div>
  )
}
