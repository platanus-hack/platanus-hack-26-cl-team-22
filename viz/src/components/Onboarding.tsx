import { useEffect, useRef, useState, type CSSProperties } from 'react'
import logoRoot from '../assets/logo-root.png'
import { componerCaso, LARGO_RESPUESTA_MAX, pedirInterpretacion, type Interpretacion } from '../lib/caso'
import { CASOS, casoDe, LARGO_CASO, leerCaso, prioridadesDe, type CasoId } from '../lib/onboarding'
import type { VariableCorta } from '../lib/variables'

export interface Busqueda {
  caso: CasoId
  /** peso de 0 a 10 por variable simulada */
  prioridades: Record<string, number>
  /** id del rango elegido por variable simulada */
  rangos: Record<string, string>
  /** el caso en palabras de la persona; vacío si no escribió nada */
  contexto: string
  /** criterios del caso que esta versión no mide */
  sinDatos: string[]
  /**
   * Claude's reading of `contexto`, when the entry already asked for it: null if that call failed,
   * absent if nobody asked yet (the map then asks itself).
   */
  lectura?: Interpretacion | null
}

interface Props {
  variables: VariableCorta[]
  onListo: (b: Busqueda) => void
  /** Where "Atrás" goes: the landing, when the simulator was opened from it. */
  inicio: string | null
  /** último año de la simulación cargada */
  hasta: number
  /** servidor-guia's /interpretar; null when no intermediary is configured. */
  urlCaso?: string | null
}

const SALIDA_MS = 520
const orden = (i: number) => ({ '--i': i }) as CSSProperties

/**
 * Entrada en una sola pantalla: el caso en texto libre. De él salen el tipo de caso y el peso de cada
 * variable, sin más preguntas; quien quiera cambiarlos lo hace después con «Ajustar pesos».
 */
export function Onboarding({ variables, onListo, inicio, hasta, urlCaso = null }: Props) {
  const [contexto, setContexto] = useState('')
  const [pensando, setPensando] = useState(false)
  const [preguntas, setPreguntas] = useState<string[]>([])
  const [respuestas, setRespuestas] = useState<string[]>([])
  const [primera, setPrimera] = useState<Interpretacion | null>(null)
  const [saliendo, setSaliendo] = useState(false)
  const hoja = useRef<HTMLDivElement>(null)
  const ids = variables.map((v) => v.id)

  useEffect(() => {
    hoja.current?.querySelector<HTMLElement>('textarea')?.focus()
  }, [])

  const cerrar = (b: Busqueda) => {
    if (saliendo) return
    setSaliendo(true)
    const quieto = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
    window.setTimeout(() => onListo(b), quieto ? 0 : SALIDA_MS)
  }
  const terminar = (texto: string, lectura?: Interpretacion | null) => {
    const caso = casoDe(texto ? leerCaso(texto) : 'general')
    cerrar({
      caso: caso.id,
      prioridades: prioridadesDe(caso, ids),
      rangos: {},
      contexto: texto,
      sinDatos: texto ? caso.referencia.map((r) => r.nombre) : [],
      ...(lectura !== undefined && { lectura }),
    })
  }
  const entrar = () => {
    if (saliendo || pensando) return
    const texto = contexto.trim()
    // Second step: the person answered (or skipped) Claude's questions. With no answers the case is
    // unchanged and the first reading still holds, so it is reused instead of asking again.
    if (preguntas.length > 0) {
      const final = componerCaso(texto, preguntas, respuestas)
      return terminar(final, final === texto ? primera : undefined)
    }
    if (!urlCaso || !texto) return terminar(texto)
    // One call reads the case and says what is missing (at most two questions). When nothing is
    // missing, that same reading goes to the map, which then skips its own call.
    const caso = casoDe(leerCaso(texto))
    setPensando(true)
    void pedirInterpretacion(urlCaso, { caso: texto, perfil: caso.titulo, prioridades: prioridadesDe(caso, ids) }).then((r) => {
      setPensando(false)
      if (!r || r.preguntas.length === 0) return terminar(texto, r)
      setPrimera(r)
      setPreguntas(r.preguntas)
      setRespuestas(r.preguntas.map(() => ''))
    })
  }

  return (
    <div className={`onb${saliendo ? ' onb-saliendo' : ''}`} role="dialog" aria-modal="true" aria-label="Antes de empezar">
      <div className="onb-marco">
        <header className="onb-cabeza">
          <p className="onb-marca">
            <img src={logoRoot} alt="root" />
          </p>
        </header>

        <div className="onb-hoja" ref={hoja}>
          <h2>¿Qué quieres evaluar?</h2>
          <p className="onb-bajada" style={orden(0)}>
            Cuéntalo con tus palabras. Con eso ordenamos las 52 comunas hasta {hasta}; los pesos se ajustan solos y puedes cambiarlos después.
          </p>
          <label className="onb-caso" style={orden(1)}>
            <span className="solo-lector">Tu caso</span>
            <textarea
              value={contexto}
              readOnly={preguntas.length > 0}
              maxLength={LARGO_CASO}
              rows={4}
              placeholder="Cuéntame qué quieres evaluar y para quién: ¿una vivienda o una empresa? ¿Hay niños, mayores o personas con asma?"
              onChange={(e) => setContexto(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  entrar()
                }
              }}
            />
            <span className="onb-cuenta" aria-hidden="true">
              {contexto.length} / {LARGO_CASO}
            </span>
          </label>
          {preguntas.length > 0 && (
            <div className="onb-preguntas" role="group" aria-label="Preguntas para entender tu caso">
              <p className="onb-bajada">Para afinar el resultado, ¿me ayudas con esto? Puedes dejarlo en blanco.</p>
              {preguntas.map((q, i) => (
                <label key={q} className="onb-pregunta">
                  <span>{q}</span>
                  <input
                    type="text"
                    value={respuestas[i] ?? ''}
                    maxLength={LARGO_RESPUESTA_MAX}
                    autoFocus={i === 0}
                    onChange={(e) => setRespuestas((r) => r.map((x, j) => (j === i ? e.target.value : x)))}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        entrar()
                      }
                    }}
                  />
                </label>
              ))}
            </div>
          )}
          <div className="onb-ejemplos" style={orden(2)} hidden={preguntas.length > 0}>
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
            <button type="button" className="onb-seguir" onClick={entrar} disabled={pensando}>
              {pensando ? 'Leyendo tu caso…' : 'Ver el mapa'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
