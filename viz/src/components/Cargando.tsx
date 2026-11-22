import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import logoRoot from '../assets/logo-root.png'
import type { Rio } from '../lib/agua'
import type { GeoFeature } from '../lib/geo'
import { cajaDePoligonos, crearProyeccion, poligonoMayor, proyectarGeometria, puntoInterior, rutaDePoligonos, type Poligono } from '../lib/proyeccion'
import { limitesDe } from '../lib/vista'

/** Qué se dibuja en el mapa de la espera cuando empieza cada paso. */
export type EtapaCarga = 'comunas' | 'rios' | 'planes' | 'riesgo'

export interface PasoCarga {
  texto: string
  /** lo que este paso espera ya ocurrió (el mapa cargó, Claude respondió…) */
  listo: boolean
  etapa?: EtapaCarga
}

interface Props {
  pasos: PasoCarga[]
  onFin: () => void
  /** la región, para dibujarla mientras se espera; sin esto queda solo la lista */
  mapa?: {
    features: readonly GeoFeature[]
    rios: readonly Rio[]
    /** clase de papel del riesgo de cada comuna (nivel-0…5); null = sin dato */
    clase: (f: GeoFeature) => string | null
    /** comunas con algún plan vigente */
    conPlan: (f: GeoFeature) => boolean
  }
}

/** cada paso se queda a la vista al menos esto, para que se alcance a leer y a ver su dibujo */
const MIN_PASO_MS = 900
/** tope: si algo no llega, se entra igual y la pantalla termina de cargar a la vista */
const TOPE_MS = 14_000
const SALIDA_MS = 520

/** Deja a lo más `max` puntos de una línea, tomando uno cada tantos y conservando el último. */
function aligerar<T>(pts: readonly T[], max: number): T[] {
  if (pts.length <= max) return [...pts]
  const paso = Math.ceil(pts.length / max)
  const out = pts.filter((_, i) => i % paso === 0)
  out.push(pts[pts.length - 1]!)
  return out
}

/**
 * Pantalla de espera entre la entrada y el mapa. Cada línea corresponde a algo que de verdad se está
 * esperando o preparando, y se marca cuando eso terminó. Al lado, la región se dibuja sola al ritmo de los
 * pasos: primero el contorno de las comunas, después los ríos, los planes y al final el color del riesgo.
 */
export function Cargando({ pasos, onFin, mapa }: Props) {
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
  // Una etapa del dibujo empieza cuando su paso pasa a ser el actual.
  const etapas = new Set(pasos.filter((p, i) => p.etapa && i <= hechos).map((p) => p.etapa))

  // Geometría proyectada una vez. El retraso de cada comuna sale de su distancia al centro: el dibujo se abre desde Santiago.
  const dibujo = useMemo(() => {
    if (!mapa || mapa.features.length === 0) return null
    const proj = crearProyeccion(limitesDe([...mapa.features]) ?? [-71.7, -34.3, -69.7, -32.9])
    const todos: Poligono[] = []
    const comunas = mapa.features.map((f) => {
      // contornos aligerados: la espera no necesita el detalle del mapa y con miles de vértices no alcanza a animarse
      const ps = proyectarGeometria(f.geometry, proj).map((pol) => pol.map((anillo) => aligerar(anillo, 160)))
      todos.push(...ps)
      const mayor = poligonoMayor(ps)
      return { f, d: rutaDePoligonos(ps), centro: mayor ? puntoInterior(mayor) : ([0, 0] as [number, number]) }
    })
    const caja = cajaDePoligonos(todos)
    if (!caja) return null
    const cx = (caja.x0 + caja.x1) / 2
    const cy = (caja.y0 + caja.y1) / 2
    const radio = Math.hypot(caja.x1 - caja.x0, caja.y1 - caja.y0) / 2 || 1
    const m = (caja.x1 - caja.x0) * 0.03
    return {
      caja: `${caja.x0 - m} ${caja.y0 - m} ${caja.x1 - caja.x0 + 2 * m} ${caja.y1 - caja.y0 + 2 * m}`,
      // grosor de un píxel aproximado en unidades del dibujo: el trazo va en esas unidades para que el
      // guion normalizado (pathLength) funcione; con trazo fijo en pantalla el navegador no alcanza a pintarlo
      px: (caja.x1 - caja.x0 + 2 * m) / 640,
      comunas: comunas.map((c) => ({
        d: c.d,
        retraso: Math.hypot(c.centro[0] - cx, c.centro[1] - cy) / radio,
        clase: mapa.clase(c.f),
        plan: mapa.conPlan(c.f),
      })),
      rios: mapa.rios.map((r) => ({
        d: aligerar(r.coords, 40).map((c, i) => `${i ? 'L' : 'M'}${proj(c[0], c[1]).map((n) => +n.toFixed(4)).join(' ')}`).join(''),
        medido: r.estacion !== null,
      })),
    }
  }, [mapa])

  return (
    <div className={`onb carga${saliendo ? ' onb-saliendo' : ''}${dibujo ? ' carga-con-mapa' : ''}`} role="status" aria-live="polite" aria-label="Preparando el análisis">
      <div className="onb-marco carga-marco">
        {dibujo && (
          <svg className={`carga-mapa${[...etapas].map((e) => ` carga-e-${e}`).join('')}`} viewBox={dibujo.caja} style={{ '--px': dibujo.px } as CSSProperties} aria-hidden="true">
            <g className="carga-comunas">
              {dibujo.comunas.map((c, i) => (
                <path key={i} d={c.d} pathLength={1} className={`${c.clase ?? 'sin-dato'}${c.plan ? ' carga-plan' : ''}`} style={{ '--r': c.retraso.toFixed(3) } as CSSProperties} />
              ))}
            </g>
            <g className="carga-rios">
              {dibujo.rios.map((r, i) => (
                <path key={i} d={r.d} pathLength={1} className={r.medido ? 'carga-rio-medido' : undefined} />
              ))}
            </g>
          </svg>
        )}
        <div className="carga-texto">
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
    </div>
  )
}
