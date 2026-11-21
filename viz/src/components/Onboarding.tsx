import { useEffect, useRef, useState, type CSSProperties } from 'react'
import logoRoot from '../assets/logo-root.png'
import {
  CASOS,
  casoDe,
  GRADOS,
  LARGO_CASO,
  LARGO_CRITERIO,
  leerCaso,
  limpiarCriterio,
  MAX_PROPIOS,
  prioridadesDe,
  rangosDe,
  type CasoId,
} from '../lib/onboarding'
import type { VariableCorta } from '../lib/variables'
import { Desplegable } from './Desplegable'

export interface Busqueda {
  caso: CasoId
  /** peso de 0 a 10 por variable simulada */
  prioridades: Record<string, number>
  /** id del rango elegido por variable simulada */
  rangos: Record<string, string>
  /** el caso en palabras de la persona; vacío si no escribió nada */
  contexto: string
  /** criterios del caso y propios que esta versión no mide */
  sinDatos: string[]
}

interface Props {
  variables: VariableCorta[]
  onListo: (b: Busqueda) => void
  /** Where "Atrás" on the first step goes: the landing, when the simulator was opened from it. */
  inicio: string | null
}

const SALIDA_MS = 520
const orden = (i: number) => ({ '--i': i }) as CSSProperties

/**
 * Entrada en dos pantallas: el caso en texto libre y, a partir de él, los criterios a medir.
 * Los simulados llevan peso y rango; los del caso y los propios se muestran sin número porque no hay datos.
 */
export function Onboarding({ variables, onListo, inicio }: Props) {
  const [paso, setPaso] = useState(0)
  const [atras, setAtras] = useState(false)
  const [contexto, setContexto] = useState('')
  const [caso, setCaso] = useState<CasoId>('general')
  const [prioridades, setPrioridades] = useState<Record<string, number>>({})
  const [rangos, setRangos] = useState<Record<string, string>>({})
  const [propios, setPropios] = useState<string[]>([])
  const [nuevo, setNuevo] = useState('')
  const [saliendo, setSaliendo] = useState(false)
  const hoja = useRef<HTMLDivElement>(null)
  const ids = variables.map((v) => v.id)
  const def = casoDe(caso)

  // Al cambiar de pantalla el foco va a su título, para teclado y lector de pantalla.
  useEffect(() => {
    hoja.current?.querySelector<HTMLElement>('h2')?.focus()
  }, [paso])

  const ponerCaso = (id: CasoId) => {
    setCaso(id)
    setPrioridades(prioridadesDe(casoDe(id), ids))
  }
  const cerrar = (b: Busqueda) => {
    if (saliendo) return
    setSaliendo(true)
    const quieto = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
    window.setTimeout(() => onListo(b), quieto ? 0 : SALIDA_MS)
  }
  const seguir = () => {
    ponerCaso(leerCaso(contexto))
    setAtras(false)
    setPaso(1)
  }
  const explorar = () => cerrar({ caso: 'general', prioridades: prioridadesDe(casoDe('general'), ids), rangos: {}, contexto: '', sinDatos: [] })
  const agregar = () => {
    const t = limpiarCriterio(nuevo, [...def.referencia.map((r) => r.nombre), ...variables.map((v) => v.nombre), ...propios])
    if (!t || propios.length >= MAX_PROPIOS) return
    setPropios((x) => [...x, t])
    setNuevo('')
  }
  const algo = Object.values(prioridades).some((v) => v > 0)

  return (
    <div className={`onb${saliendo ? ' onb-saliendo' : ''}`} role="dialog" aria-modal="true" aria-label="Antes de empezar">
      <div className="onb-marco">
        <header className="onb-cabeza">
          <p className="onb-marca">
            <img src={logoRoot} alt="root" />
          </p>
          <ol className="onb-pasos" aria-label={`Paso ${paso + 1} de 2`}>
            {[0, 1].map((i) => (
              <li key={i} className={i === paso ? 'onb-paso-actual' : i < paso ? 'onb-paso-hecho' : undefined} />
            ))}
          </ol>
        </header>

        <div className={`onb-hoja${atras ? ' onb-atras' : ''}`} key={paso} ref={hoja}>
          {paso === 0 && (
            <>
              <h2 tabIndex={-1}>¿Qué quieres evaluar?</h2>
              <p className="onb-bajada" style={orden(0)}>
                Cuéntalo con tus palabras. De ahí salen los criterios para comparar las 52 comunas hasta 2036.
              </p>
              <label className="onb-caso" style={orden(1)}>
                <span className="solo-lector">Tu caso</span>
                <textarea
                  value={contexto}
                  maxLength={LARGO_CASO}
                  rows={3}
                  placeholder="Quiero…"
                  onChange={(e) => setContexto(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      seguir()
                    }
                  }}
                />
                <span className="onb-cuenta" aria-hidden="true">
                  {contexto.length} / {LARGO_CASO}
                </span>
              </label>
              <div className="onb-ejemplos" style={orden(2)}>
                <span>Por ejemplo:</span>
                {CASOS.filter((c) => c.ejemplo).map((c) => (
                  <button key={c.id} type="button" className="onb-chip" onClick={() => setContexto(c.ejemplo)}>
                    {c.titulo}
                  </button>
                ))}
              </div>
              <div className="onb-pie" style={orden(3)}>
                {inicio && (
                  <a className="onb-volver" href={inicio}>
                    Atrás
                  </a>
                )}
                <button type="button" className="onb-volver" onClick={explorar}>
                  Entrar sin responder
                </button>
                <button type="button" className="onb-seguir" onClick={seguir}>
                  Seguir
                </button>
              </div>
            </>
          )}

          {paso === 1 && (
            <>
              <h2 tabIndex={-1}>Esto vamos a medir</h2>
              <div className="onb-lectura" style={orden(0)} role="radiogroup" aria-label="Cómo se leyó tu caso">
                <span>Leímos tu caso como</span>
                {CASOS.map((c) => (
                  <button key={c.id} type="button" role="radio" aria-checked={c.id === caso} className="onb-chip" onClick={() => ponerCaso(c.id)}>
                    {c.titulo}
                  </button>
                ))}
              </div>

              <section className="onb-grupo" style={orden(1)} aria-labelledby="onb-g1">
                <h3 id="onb-g1">
                  Simulado por el modelo <span>cambia el resultado</span>
                </h3>
                {variables.map((v) => (
                  <div className="onb-criterio" key={v.id}>
                    <p>
                      <b>{v.nombre}</b>
                      <span>{v.que}</span>
                    </p>
                    <div className="onb-grados" role="radiogroup" aria-label={`Peso de ${v.nombre.toLowerCase()}`}>
                      {GRADOS.map((g) => (
                        <button
                          key={g.valor}
                          type="button"
                          role="radio"
                          aria-checked={prioridades[v.id] === g.valor}
                          className="onb-grado"
                          onClick={() => setPrioridades((x) => ({ ...x, [v.id]: g.valor }))}
                        >
                          {g.texto}
                        </button>
                      ))}
                    </div>
                    <Desplegable
                      etiqueta="Rango"
                      valor={rangos[v.id] ?? 'libre'}
                      onCambiar={(id) => setRangos((x) => ({ ...x, [v.id]: id }))}
                      opciones={rangosDe(v.id).map((o) => ({ id: o.id, titulo: o.titulo, detalle: o.detalle }))}
                    />
                  </div>
                ))}
              </section>

              <section className="onb-grupo" style={orden(2)} aria-labelledby="onb-g2">
                <h3 id="onb-g2">
                  Para tu caso <span>aún sin datos: no entra al cálculo</span>
                </h3>
                <ul className="onb-referencias">
                  {def.referencia.map((r) => (
                    <li key={r.id}>
                      <b>{r.nombre}</b>
                      <span>
                        {r.que}
                        {r.unidad ? ` · ${r.unidad}` : ''}
                      </span>
                    </li>
                  ))}
                  {propios.map((t) => (
                    <li key={t} className="onb-propio">
                      <b>{t}</b>
                      <span>Criterio tuyo</span>
                      <button type="button" aria-label={`Quitar ${t}`} onClick={() => setPropios((x) => x.filter((y) => y !== t))}>
                        ×
                      </button>
                    </li>
                  ))}
                  {propios.length < MAX_PROPIOS && (
                    <li className="onb-agregar">
                      <input
                        type="text"
                        value={nuevo}
                        maxLength={LARGO_CRITERIO}
                        placeholder="Agregar un criterio propio"
                        aria-label="Agregar un criterio propio"
                        onChange={(e) => setNuevo(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault()
                            agregar()
                          }
                        }}
                      />
                      <button type="button" disabled={!nuevo.trim()} onClick={agregar}>
                        Agregar
                      </button>
                    </li>
                  )}
                </ul>
              </section>

              <div className="onb-pie" style={orden(3)}>
                <button
                  type="button"
                  className="onb-volver"
                  onClick={() => {
                    setAtras(true)
                    setPaso(0)
                  }}
                >
                  Atrás
                </button>
                <button
                  type="button"
                  className="onb-seguir"
                  disabled={!algo}
                  onClick={() => cerrar({ caso, prioridades, rangos, contexto: contexto.trim(), sinDatos: [...def.referencia.map((r) => r.nombre), ...propios] })}
                >
                  Ver el mapa
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
