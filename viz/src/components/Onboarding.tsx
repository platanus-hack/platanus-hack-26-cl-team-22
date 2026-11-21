import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { GRADOS, LARGO_CASO, PERFILES, prioridadesDe, type Perfil, type PerfilId } from '../lib/onboarding'
import type { VariableCorta } from '../lib/variables'

export interface Busqueda {
  perfil: PerfilId
  prioridades: Record<string, number>
  /** el caso en palabras de la persona; vacío si no escribió nada */
  contexto: string
}

interface Props {
  variables: VariableCorta[]
  onListo: (b: Busqueda) => void
}

const SALIDA_MS = 520
const orden = (i: number) => ({ '--i': i }) as CSSProperties

/**
 * Entrada en tres pantallas, una decisión por pantalla: quién busca, qué pesa más y, si quiere, su caso.
 * Elegir una tarjeta avanza sola; «Solo quiero explorar» entra directo al mapa.
 */
export function Onboarding({ variables, onListo }: Props) {
  const [paso, setPaso] = useState(0)
  const [atras, setAtras] = useState(false)
  const [perfil, setPerfil] = useState<Perfil | null>(null)
  const [prioridades, setPrioridades] = useState<Record<string, number>>({})
  const [contexto, setContexto] = useState('')
  const [saliendo, setSaliendo] = useState(false)
  const hoja = useRef<HTMLDivElement>(null)
  const ids = variables.map((v) => v.id)

  // Al cambiar de pantalla el foco va a su título, para teclado y lector de pantalla.
  useEffect(() => {
    hoja.current?.querySelector<HTMLElement>('h2')?.focus()
  }, [paso])

  const ir = (n: number) => {
    setAtras(n < paso)
    setPaso(n)
  }
  const cerrar = (b: Busqueda) => {
    if (saliendo) return
    setSaliendo(true)
    const quieto = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
    window.setTimeout(() => onListo(b), quieto ? 0 : SALIDA_MS)
  }
  const elegir = (p: Perfil) => {
    const pr = prioridadesDe(p, ids)
    setPerfil(p)
    setPrioridades(pr)
    if (p.id === 'explorar') cerrar({ perfil: p.id, prioridades: pr, contexto: '' })
    else ir(1)
  }
  const algo = Object.values(prioridades).some((v) => v > 0)
  const terminar = (conCaso: boolean) => perfil && cerrar({ perfil: perfil.id, prioridades, contexto: conCaso ? contexto.trim() : '' })

  return (
    <div className={`onb${saliendo ? ' onb-saliendo' : ''}`} role="dialog" aria-modal="true" aria-label="Antes de empezar">
      <div className="onb-marco">
        <header className="onb-cabeza">
          <p className="onb-marca">root</p>
          <ol className="onb-pasos" aria-label={`Paso ${paso + 1} de 3`}>
            {[0, 1, 2].map((i) => (
              <li key={i} className={i === paso ? 'onb-paso-actual' : i < paso ? 'onb-paso-hecho' : undefined} />
            ))}
          </ol>
        </header>

        <div className={`onb-hoja${atras ? ' onb-atras' : ''}`} key={paso} ref={hoja}>
          {paso === 0 && (
            <>
              <h2 tabIndex={-1}>¿Qué estás buscando?</h2>
              <p className="onb-bajada" style={orden(0)}>
                52 comunas de la Región Metropolitana, simuladas hasta 2036.
              </p>
              <div className="onb-tarjetas">
                {PERFILES.map((p, i) => (
                  <button key={p.id} type="button" className="onb-tarjeta" style={orden(i + 1)} onClick={() => elegir(p)}>
                    <span className="onb-num">{i + 1}</span>
                    <b>{p.titulo}</b>
                    <span>{p.bajada}</span>
                  </button>
                ))}
              </div>
            </>
          )}

          {paso === 1 && perfil && (
            <>
              <h2 tabIndex={-1}>¿Qué pesa más para ti?</h2>
              <p className="onb-bajada" style={orden(0)}>
                Partimos de lo habitual para «{perfil.titulo.toLowerCase()}». Cámbialo si quieres.
              </p>
              <div className="onb-variables">
                {variables.map((v, i) => (
                  <div className="onb-variable" key={v.id} style={orden(i + 1)} role="radiogroup" aria-label={`Peso de ${v.nombre.toLowerCase()}`}>
                    <p>
                      <b>{v.nombre}</b>
                      <span>{v.que}</span>
                    </p>
                    <div className="onb-grados">
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
                  </div>
                ))}
              </div>
              <div className="onb-pie" style={orden(variables.length + 1)}>
                <button type="button" className="onb-volver" onClick={() => ir(0)}>
                  Atrás
                </button>
                <button type="button" className="onb-seguir" disabled={!algo} onClick={() => ir(2)}>
                  Seguir
                </button>
              </div>
            </>
          )}

          {paso === 2 && perfil && (
            <>
              <h2 tabIndex={-1}>Cuéntanos tu caso</h2>
              <p className="onb-bajada" style={orden(0)}>
                Opcional. Una frase basta para afinar la recomendación.
              </p>
              <label className="onb-caso" style={orden(1)}>
                <span className="solo-lector">Tu caso</span>
                <textarea value={contexto} maxLength={LARGO_CASO} rows={3} placeholder={perfil.ejemplo} onChange={(e) => setContexto(e.target.value)} />
                <span className="onb-cuenta" aria-hidden="true">
                  {contexto.length} / {LARGO_CASO}
                </span>
              </label>
              {perfil.ejemplo && !contexto && (
                <button type="button" className="onb-ejemplo" style={orden(2)} onClick={() => setContexto(perfil.ejemplo)}>
                  Usar el ejemplo
                </button>
              )}
              <div className="onb-pie" style={orden(3)}>
                <button type="button" className="onb-volver" onClick={() => ir(1)}>
                  Atrás
                </button>
                <button type="button" className="onb-volver" onClick={() => terminar(false)}>
                  Saltar
                </button>
                <button type="button" className="onb-seguir" onClick={() => terminar(true)}>
                  Ver mi mapa
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
