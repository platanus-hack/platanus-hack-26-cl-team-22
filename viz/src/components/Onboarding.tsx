import { useEffect, useRef, useState, type CSSProperties } from 'react'
import logoRoot from '../assets/logo-root.png'
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
}

interface Props {
  variables: VariableCorta[]
  onListo: (b: Busqueda) => void
  /** Where "Atrás" goes: the landing, when the simulator was opened from it. */
  inicio: string | null
}

const SALIDA_MS = 520
const orden = (i: number) => ({ '--i': i }) as CSSProperties

/**
 * Entrada en una sola pantalla: el caso en texto libre. De él salen el tipo de caso y el peso de cada
 * variable, sin más preguntas; quien quiera cambiarlos lo hace después con «Ajustar pesos».
 */
export function Onboarding({ variables, onListo, inicio }: Props) {
  const [contexto, setContexto] = useState('')
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
  const entrar = () => {
    const texto = contexto.trim()
    const caso = casoDe(texto ? leerCaso(texto) : 'general')
    cerrar({
      caso: caso.id,
      prioridades: prioridadesDe(caso, ids),
      rangos: {},
      contexto: texto,
      sinDatos: texto ? caso.referencia.map((r) => r.nombre) : [],
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
            Cuéntalo con tus palabras. Con eso ordenamos las 52 comunas hasta 2036; los pesos se ajustan solos y puedes cambiarlos después.
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
                  entrar()
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
            <button type="button" className="onb-seguir" onClick={entrar}>
              Ver el mapa
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
