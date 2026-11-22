import type { ReactNode } from 'react'
import { safeUrl } from '../lib/format'
import type { DefPestana, DefSeccion, SeccionId } from '../lib/pestanas'
import type { Politica } from '../lib/types'

interface Props {
  pestana: DefPestana
  secciones: DefSeccion[]
  abierta: SeccionId | null
  onSeccion: (id: SeccionId) => void
  children: ReactNode
}

/**
 * Marco de una hoja: título y subtítulo que dicen de qué trata y, si tiene varias secciones,
 * un acordeón con una sola abierta. El contenido es el de la sección abierta.
 */
export function Hoja({ pestana, secciones, abierta, onSeccion, children }: Props) {
  return (
    <div className="hoja-marco">
      {pestana.titulo && (
        <header className="hoja-cabeza">
          <h2>{pestana.titulo}</h2>
          {pestana.subtitulo && <p>{pestana.subtitulo}</p>}
        </header>
      )}
      {secciones.length > 1 ? (
        <div className="acordeon">
          {secciones.map((s) => {
            const esta = s.id === abierta
            return (
              <section key={s.id} className={`pliegue${esta ? ' pliegue-abierto' : ''}`}>
                <h3>
                  <button type="button" aria-expanded={esta} aria-controls={`pliegue-${s.id}`} onClick={() => onSeccion(s.id)}>
                    <span>{s.titulo}</span>
                    <svg viewBox="0 0 12 8" aria-hidden="true">
                      <path d="M1 1.5 L6 6.5 L11 1.5" />
                    </svg>
                  </button>
                </h3>
                {esta && (
                  <div className="pliegue-cuerpo" id={`pliegue-${s.id}`}>
                    {children}
                  </div>
                )}
              </section>
            )
          })}
        </div>
      ) : (
        children
      )}
    </div>
  )
}

/** Fuentes públicas de los datos (las mismas del README del proyecto). */
const FUENTES: readonly { sigla: string; que: string }[] = [
  { sigla: 'SINCA, Ministerio del Medio Ambiente', que: 'PM2,5 medido por estación.' },
  { sigla: 'RETC', que: 'Emisiones por comuna y por fuente.' },
  { sigla: 'INE', que: 'Censos 2017 y 2024.' },
  { sigla: 'CEAD', que: 'Delitos de mayor connotación social por comuna.' },
  { sigla: 'ECOS-Chile y SMA', que: 'Cumplimiento del plan de descontaminación.' },
  { sigla: 'DGA, compilación (CR)2', que: 'Caudal medio mensual por estación, 1980–2017 (CC0).' },
  { sigla: 'OpenStreetMap', que: 'Trazado de los ríos (ODbL).' },
]

/** Quita las rutas internas del repo que algunas citas traen entre paréntesis: no le dicen nada a quien lee. */
const limpiarCita = (c: string | undefined): string => (c ?? '').replace(/\s*\((?:data|docs|results)\/[^)]*\)/g, '')

/** Bibliografía: fuentes de datos y la cita de cada plan o medida que el modelo usa. */
export function VistaFuentes({ politicas }: { politicas: Politica[] }) {
  const citas = politicas.filter((p) => p.cita)
  return (
    <div className="v-fuentes">
      <ul className="fuentes">
        {FUENTES.map((f) => (
          <li key={f.sigla}>
            <b>{f.sigla}</b>
            <span>{f.que}</span>
          </li>
        ))}
      </ul>
      {citas.length > 0 && (
        <details className="limites fuentes-planes">
          <summary>Normas y estudios detrás de cada plan ({citas.length})</summary>
          <ul className="fuentes">
            {citas.map((p) => {
              const url = safeUrl(p.url)
              return (
                <li key={p.id}>
                  <b>{p.nombre.replace(/\s*\((propuesta|ilustrativa)\)\s*$/i, '')}</b>
                  <span>
                    {url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer">
                        {limpiarCita(p.cita)}
                      </a>
                    ) : (
                      limpiarCita(p.cita)
                    )}
                  </span>
                </li>
              )
            })}
          </ul>
        </details>
      )}
    </div>
  )
}
