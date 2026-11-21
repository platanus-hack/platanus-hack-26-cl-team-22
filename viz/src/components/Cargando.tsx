import { useEffect, useRef, useState } from 'react'
import logoRoot from '../assets/logo-root.png'

export interface PasoCarga {
  texto: string
  /** lo que este paso espera ya ocurrió (el mapa cargó, Claude respondió…) */
  listo: boolean
}

interface Props {
  pasos: PasoCarga[]
  onFin: () => void
}

/** cada paso se queda a la vista al menos esto, para que se alcance a leer */
const MIN_PASO_MS = 520
/** tope: si algo no llega, se entra igual y la pantalla termina de cargar a la vista */
const TOPE_MS = 12_000
const SALIDA_MS = 520

/**
 * Pantalla de espera entre la entrada y el mapa. Cada línea corresponde a algo que de verdad se está
 * esperando o preparando, y se marca cuando eso terminó: así la persona ve avanzar el trabajo en vez de un
 * mapa a medio cargar.
 */
export function Cargando({ pasos, onFin }: Props) {
  const [hechos, setHechos] = useState(0)
  const [saliendo, setSaliendo] = useState(false)
  const inicio = useRef(performance.now())
  const fin = useRef(onFin)
  fin.current = onFin
  const quieto = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches

  // Avanza un paso cuando lo que espera está listo (o venció el tope), dejando un mínimo para leerlo.
  const actualListo = pasos[hechos]?.listo ?? true
  useEffect(() => {
    if (hechos >= pasos.length) return
    const vencido = performance.now() - inicio.current > TOPE_MS
    if (!actualListo && !vencido) {
      // Sigue esperando: el efecto vuelve a correr cuando `listo` cambia; el tope evita quedarse aquí.
      const tope = window.setTimeout(() => setHechos((n) => n + 1), Math.max(0, TOPE_MS - (performance.now() - inicio.current)))
      return () => window.clearTimeout(tope)
    }
    const t = window.setTimeout(() => setHechos((n) => n + 1), quieto ? 0 : MIN_PASO_MS)
    return () => window.clearTimeout(t)
  }, [hechos, actualListo, pasos.length, quieto])

  useEffect(() => {
    if (hechos < pasos.length) return
    setSaliendo(true)
    const t = window.setTimeout(() => fin.current(), quieto ? 0 : SALIDA_MS)
    return () => window.clearTimeout(t)
  }, [hechos, pasos.length, quieto])

  const avance = pasos.length > 0 ? Math.min(1, hechos / pasos.length) : 1

  return (
    <div className={`onb carga${saliendo ? ' onb-saliendo' : ''}`} role="status" aria-live="polite" aria-label="Preparando el análisis">
      <div className="onb-marco carga-marco">
        <p className="onb-marca">
          <img src={logoRoot} alt="root" />
        </p>
        <h2 className="carga-titulo">Preparando tu análisis</h2>
        <div className="carga-barra" aria-hidden="true">
          <i style={{ transform: `scaleX(${avance})` }} />
        </div>
        <ol className="carga-pasos">
          {pasos.map((p, i) => (
            <li key={p.texto} className={i < hechos ? 'carga-hecho' : i === hechos ? 'carga-actual' : 'carga-pendiente'}>
              <svg viewBox="0 0 16 16" aria-hidden="true">
                {i < hechos ? <path d="M3 8.5 L6.5 12 L13 4.5" /> : <circle cx="8" cy="8" r="5" />}
              </svg>
              {p.texto}
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}
