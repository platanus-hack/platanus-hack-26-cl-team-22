import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { anchoRio, estadoCaudal, radioEstacion, type CauceDato, type EstadoCaudal, type Estacion, type Rio } from '../lib/agua'
import type { AportePolitica } from '../lib/capas'
import { apilarLabios, apilarNivel, PAPELES_POLITICA } from '../lib/capas'
import type { Punto } from '../lib/data'
import type { Diferencia } from '../lib/diferencia'
import { claseFondo as claseDeFondo, type ModoMapa } from '../lib/fondo'
import { escalarAnillo, rutaFestoneada } from '../lib/feston'
import type { GeoFeature } from '../lib/geo'
import { radioDisco, type Lena } from '../lib/lena'
import { papelNivel } from '../lib/niveles'
import {
  ajustarCaja,
  areaAnillo,
  cajaDePoligonos,
  crearProyeccion,
  interpolarVista,
  limitarVista,
  poligonoMayor,
  proyectarGeometria,
  puntoInterior,
  rutaCurva,
  rutaDePoligonos,
  zoomEn,
  type Caja,
  type Poligono,
  type Pt,
  type Vista,
} from '../lib/proyeccion'
import type { Mejor } from '../lib/types'
import type { EstadoTransicionMapa } from '../lib/transicion'
import { TarjetaMapa, type Etiqueta } from './Papel'
import { esGranSantiago, limitesDe } from '../lib/vista'

export type { ModoMapa }
export type Encuadre = 'gran-santiago' | 'region'

export interface Cinta {
  desde: string
  fraccion: number
}

/** Lo que el mapa necesita para dibujar el agua: cauces, estaciones y el año que se mira. */
export interface AguaMapa {
  rios: readonly Rio[]
  estaciones: readonly Estacion[]
  cauces: readonly CauceDato[]
  /** comunas por donde pasa el río elegido */
  pasa: ReadonlySet<string>
  porCodigo: ReadonlyMap<string, Estacion>
  /** caudal (m³/s) y caudal sobre lo normal de una estación en lo que se mira, medido o simulado; null = sin dato */
  caudalDe: (e: Estacion) => number | null
  fraccionDe: (e: Estacion) => number | null
  /** cambia cuando cambia lo que se mira: los mapas vuelven a pintar */
  clave: string
  elegida: string | null
  onElegir: (codigo: string) => void
  etiqueta: (e: Estacion) => Etiqueta
}

/** Caudal con que se dibuja un cauce en el año mostrado; null si ninguna estación lo mide. */
export function caudalDeRio(r: Rio, a: AguaMapa): number | null {
  const e = r.estacion ? a.porCodigo.get(r.estacion) : undefined
  return e ? (a.caudalDe(e) ?? e.medio) : null
}

/** Estado del caudal de un cauce en lo que se mira; los que nadie mide se dibujan como normales. */
export function estadoDeRio(r: Rio, a: AguaMapa): EstadoCaudal {
  const e = r.estacion ? a.porCodigo.get(r.estacion) : undefined
  return e ? estadoCaudal(a.fraccionDe(e)) : 'normal'
}

export interface PropsMapa {
  features: GeoFeature[]
  modo: ModoMapa
  cortes: readonly number[]
  puntos: ReadonlyMap<string, Punto>
  difs: ReadonlyMap<string, Diferencia> | null
  difMax: number
  mejor: Mejor
  aportes: ReadonlyMap<string, AportePolitica[]>
  activas: ReadonlySet<string>
  lena: Lena | null
  /** ríos y estaciones; solo se dibujan en el modo «agua» */
  agua: AguaMapa | null
  seleccionada: string | null
  cintas: Cinta[]
  encuadre: Encuadre
  reencuadre: number
  reducido: boolean
  transicion?: EstadoTransicionMapa
  onSeleccionar: (codigo: string) => void
  /** el mapa ya tiene algo que mostrar: la pantalla de espera puede seguir */
  onListo?: () => void
  etiqueta: (f: GeoFeature) => Etiqueta
  nombreAccesible: (f: GeoFeature) => string
  children?: ReactNode
}

interface Prep {
  f: GeoFeature
  /** código de la simulación; undefined = sin dato */
  sim?: string
  d: string
  mayor: Poligono | null
  centro: Pt
  /** radio equivalente de la parte principal (unidades de mundo) */
  radio: number
}

const MARGEN = 0.045
const DURACION_ENCUADRE = 750
const facil = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t))

export function MapaPapel(p: PropsMapa) {
  const caja = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const [tam, setTam] = useState({ w: 0, h: 0 })
  const [vista, setVista] = useState<Vista | null>(null)
  const vistaRef = useRef<Vista | null>(null)
  const anim = useRef<number | null>(null)
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null)
  const [foco, setFoco] = useState<number | null>(null)
  const arrastre = useRef<{ x: number; y: number; v: Vista; movido: boolean } | null>(null)

  // Proyección y geometría, una sola vez por conjunto de polígonos.
  const { prep, cajaRegion, cajaGS, orden, proj } = useMemo(() => {
    const lim = limitesDe(p.features) ?? [-71.7, -34.3, -69.7, -32.9]
    const proj = crearProyeccion(lim)
    const prep: Prep[] = []
    const todos: Poligono[] = []
    const gs: Pt[] = []
    for (const f of p.features) {
      const ps = proyectarGeometria(f.geometry, proj)
      if (ps.length === 0) continue
      const mayor = poligonoMayor(ps)
      const centro: Pt = mayor ? puntoInterior(mayor) : [0, 0]
      todos.push(...ps)
      if (esGranSantiago(f.properties)) gs.push(centro)
      const radio = mayor ? Math.sqrt(Math.abs(areaAnillo(mayor[0]!)) / Math.PI) : 0
      prep.push({ f, sim: f.properties.simCodigo, d: rutaDePoligonos(ps), mayor, centro, radio })
    }
    const cajaRegion = cajaDePoligonos(todos) ?? { x0: 0, y0: 0, x1: 1, y1: 1 }
    // Gran Santiago: la caja de los centros de sus comunas, con holgura. Los polígonos completos
    // la inflarían (Lo Barnechea llega a la cordillera) y la ciudad quedaría chica.
    const cg = cajaDePoligonos([[gs]])
    const holgura = (cajaRegion.x1 - cajaRegion.x0) * 0.035
    const cajaGS = cg && gs.length >= 3 ? { x0: cg.x0 - holgura, y0: cg.y0 - holgura, x1: cg.x1 + holgura, y1: cg.y1 + holgura } : cajaRegion
    // Orden de pegado: primero lo de abajo a la derecha, para que el canto de cada pila caiga sobre su vecina.
    const orden = prep.map((_, i) => i).sort((a, b) => prep[b]!.centro[0] + prep[b]!.centro[1] - (prep[a]!.centro[0] + prep[a]!.centro[1]))
    return { prep, cajaRegion, cajaGS, orden, proj }
  }, [p.features])

  // Ríos proyectados una vez; el ancho depende del año y se calcula al dibujar.
  const rios = useMemo(
    () =>
      p.modo === 'agua' && p.agua
        ? p.agua.rios.map((r) => ({
            r,
            d: r.coords.map((c, i) => `${i ? 'L' : 'M'}${proj(c[0], c[1]).map((n) => +n.toFixed(5)).join(' ')}`).join(''),
          }))
        : [],
    [p.modo, p.agua?.rios, proj],
  )
  const [sobreEstacion, setSobreEstacion] = useState<{ e: Estacion; x: number; y: number } | null>(null)

  // El mapa plano no espera a nadie: está listo al montarse.
  useEffect(() => {
    p.onListo?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const porSim = useMemo(() => {
    const m = new Map<string, Prep>()
    for (const x of prep) if (x.sim) m.set(x.sim, x)
    return m
  }, [prep])

  useEffect(() => {
    const el = caja.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => {
      if (e) setTam({ w: Math.round(e.contentRect.width), h: Math.round(e.contentRect.height) })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const objetivo = useCallback(
    (enc: Encuadre): Vista => {
      const c: Caja = enc === 'region' ? cajaRegion : cajaGS
      const m = Math.min(tam.w, tam.h) * MARGEN
      // En la región completa la leyenda no debe tapar el mapa: se deja libre su alto abajo.
      const leyenda = enc === 'region' ? (caja.current?.querySelector('.leyenda')?.getBoundingClientRect().height ?? 0) : 0
      const sup = (caja.current?.querySelector('.controles-mapa')?.getBoundingClientRect().height ?? 0) + m
      return ajustarCaja(c, tam.w, tam.h, { izq: m, der: m, sup: Math.max(m * 1.8, sup), inf: Math.max(m * 1.2, leyenda + m * 0.8) })
    },
    [cajaRegion, cajaGS, tam],
  )

  const limites = useCallback(
    (v: Vista) => {
      const kMin = objetivo('region').k * 0.8
      const kMax = objetivo('gran-santiago').k * 6
      return limitarVista(v, cajaRegion, tam.w, tam.h, kMin, kMax, Math.min(tam.w, tam.h) * 0.2)
    },
    [objetivo, cajaRegion, tam],
  )

  const fijar = (v: Vista) => {
    vistaRef.current = v
    setVista(v)
  }

  // Encuadre: animado entre Gran Santiago y la región; al cambiar el tamaño, sin animación.
  const ultimoTam = useRef(tam)
  useEffect(() => {
    if (tam.w === 0 || tam.h === 0) return
    const fin = objetivo(p.encuadre)
    const ini = vistaRef.current
    const cambioTam = ultimoTam.current.w !== tam.w || ultimoTam.current.h !== tam.h
    ultimoTam.current = tam
    if (anim.current !== null) cancelAnimationFrame(anim.current)
    if (!ini || cambioTam || p.reducido) {
      fijar(fin)
      return
    }
    const t0 = performance.now()
    const paso = (ahora: number) => {
      const t = Math.min(1, (ahora - t0) / DURACION_ENCUADRE)
      fijar(interpolarVista(ini, fin, facil(t), tam.w, tam.h))
      anim.current = t < 1 ? requestAnimationFrame(paso) : null
    }
    anim.current = requestAnimationFrame(paso)
    return () => {
      if (anim.current !== null) cancelAnimationFrame(anim.current)
    }
    // reencuadre fuerza volver al encuadre aunque no cambie
  }, [p.encuadre, p.reencuadre, objetivo, tam, p.reducido])

  // Rueda: zoom alrededor del puntero (listener no pasivo para poder evitar el desplazamiento de la página).
  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    const rueda = (e: WheelEvent) => {
      e.preventDefault()
      const v = vistaRef.current
      if (!v) return
      if (anim.current !== null) cancelAnimationFrame(anim.current)
      const r = el.getBoundingClientRect()
      fijar(limites(zoomEn(v, Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top)))
    }
    el.addEventListener('wheel', rueda, { passive: false })
    return () => el.removeEventListener('wheel', rueda)
  }, [limites])

  const abajo = (e: React.PointerEvent) => {
    if (!vistaRef.current || e.button !== 0) return
    arrastre.current = { x: e.clientX, y: e.clientY, v: vistaRef.current, movido: false }
  }
  const mover = (e: React.PointerEvent) => {
    const a = arrastre.current
    if (a) {
      const dx = e.clientX - a.x
      const dy = e.clientY - a.y
      if (!a.movido && Math.hypot(dx, dy) > 4) {
        a.movido = true
        svgRef.current?.setPointerCapture(e.pointerId)
        if (anim.current !== null) cancelAnimationFrame(anim.current)
      }
      if (a.movido) fijar(limites({ k: a.v.k, tx: a.v.tx + dx, ty: a.v.ty + dy }))
    }
  }
  const arriba = (e: React.PointerEvent) => {
    if (svgRef.current?.hasPointerCapture(e.pointerId)) svgRef.current.releasePointerCapture(e.pointerId)
    setTimeout(() => {
      arrastre.current = null
    }, 0)
  }
  const clic = (x: Prep) => {
    if (arrastre.current?.movido) return
    if (x.sim) p.onSeleccionar(x.sim)
  }

  const v = vista
  const k = v?.k ?? 1
  // Retraso del despegue: primero lo más cercano a la columna de la derecha.
  const retraso = (c: Pt) => {
    if (!v || tam.w === 0) return 0
    const sx = c[0] * v.k + v.tx
    return Math.round(Math.min(1, Math.max(0, (tam.w - sx) / tam.w)) * 260)
  }

  const claseFondo = (x: Prep): string => claseDeFondo({ ...p, pasa: p.agua?.pasa }, x.f.properties.codigo, x.sim)

  const tMaxLena = useMemo(() => Math.max(0, ...(p.lena?.comunas.map((c) => c.toneladas ?? 0) ?? [0])), [p.lena])
  const radioLena = (cajaRegion.x1 - cajaRegion.x0) * 0.038
  const paso = (cajaRegion.x1 - cajaRegion.x0) * 0.0042
  // Canto de las hojas de política: proporcional al aporte, entre un mínimo y un máximo (unidades de mundo).
  const labioMax = (cajaRegion.x1 - cajaRegion.x0) * 0.0068
  const labioMin = labioMax * 0.45
  const deltaMax = useMemo(() => {
    let m = 0
    for (const l of p.aportes.values()) for (const a of l) m = Math.max(m, Math.abs(a.delta))
    return m
  }, [p.aportes])

  // Geometría que no depende del encuadre: se calcula una vez por dato, no en cada cuadro de animación.
  const recortes = useMemo(() => {
    const out: { i: number; d: string; nivel: number; centro: Pt }[] = []
    prep.forEach((x, i) => {
      if (!x.sim || !x.mayor) return
      const c = apilarNivel(p.puntos.get(x.sim), p.cortes).cruce
      if (c) out.push({ i, d: rutaFestoneada(escalarAnillo(x.mayor[0]!, x.centro, c.escala), paso), nivel: papelNivel(c.nivel, p.cortes), centro: x.centro })
    })
    return out
  }, [prep, p.puntos, p.cortes, paso])

  const sel = p.seleccionada ? porSim.get(p.seleccionada) : undefined
  const hov = hover ? prep[hover.i] : undefined
  const tag = hov ? p.etiqueta(hov.f) : null
  const enfocado = foco !== null ? prep[foco] : undefined

  return (
    <div className="mapa" ref={caja}>
      <svg
        ref={svgRef}
        className={`mapa-svg modo-${p.modo}`}
        width={tam.w}
        height={tam.h}
        viewBox={`0 0 ${tam.w} ${tam.h}`}
        role="group"
        aria-label="Mapa de comunas de la Región Metropolitana"
        onPointerDown={abajo}
        onPointerMove={mover}
        onPointerUp={arriba}
        onPointerCancel={arriba}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <filter id="alzado" x="-5%" y="-5%" width="115%" height="115%">
            <feDropShadow dx="1" dy="1" stdDeviation="0" floodColor="#111111" floodOpacity="0.2" />
          </filter>
        </defs>
        {v && (
          <g transform={`translate(${v.tx} ${v.ty}) scale(${v.k})`}>
            {/* Respaldo: la región recortada sobre una hoja de tinta, con filo blanco */}
            <g className="respaldo" aria-hidden="true">
              {prep.map((x, i) => (
                <path key={i} d={x.d} className="respaldo-tinta" />
              ))}
              {prep.map((x, i) => (
                <path key={i} d={x.d} className="respaldo-filo" />
              ))}
            </g>

            {/* Papel de nivel (o de diferencia, o de zona) de cada comuna */}
            {/* Cada comuna es una pila: las hojas de política (frías) asoman por su canto bajo el papel de nivel */}
            <g className="papeles">
              {orden.map((i) => {
                const x = prep[i]!
                const interactiva = p.modo === 'lena' || !!x.sim
                const ap = p.modo !== 'lena' && x.sim ? p.aportes.get(x.sim) : undefined
                // Solo la comuna elegida muestra su pila de hojas: así es la única que sobresale del mapa.
                const elegida = !!x.sim && x.sim === p.seleccionada
                const labios = ap && elegida ? apilarLabios(ap, p.activas, deltaMax, labioMin * 1.7, labioMax * 1.7) : []
                const salida = labioMax * 5
                return (
                  <g key={i}>
                  {[...labios].reverse().map((l) => (
                    <path
                      key={l.politicaId}
                      d={x.d}
                      aria-hidden="true"
                      className={`labio pol-${l.indice % PAPELES_POLITICA}${l.pegada ? '' : ' despegada'}`}
                      style={
                        {
                          '--d': `${retraso(x.centro)}ms`,
                          transform: `translate(${l.corrimiento + (l.pegada ? 0 : salida)}px, ${l.corrimiento + (l.pegada ? 0 : salida)}px)`,
                        } as CSSProperties
                      }
                    />
                  ))}
                  <path
                    key={i}
                    d={x.d}
                    className={`papel ${claseFondo(x)}${interactiva ? ' interactiva' : ''}`}
                    style={{ '--d': `${retraso(x.centro)}ms` } as CSSProperties}
                    tabIndex={interactiva ? 0 : undefined}
                    role={interactiva ? 'button' : undefined}
                    aria-label={interactiva ? p.nombreAccesible(x.f) : undefined}
                    aria-pressed={interactiva && x.sim ? x.sim === p.seleccionada : undefined}
                    onPointerEnter={(e) => setHover({ i, x: e.clientX, y: e.clientY })}
                    onPointerMove={(e) => setHover({ i, x: e.clientX, y: e.clientY })}
                    onClick={() => clic(x)}
                    onFocus={() => setFoco(i)}
                    onBlur={() => setFoco((f) => (f === i ? null : f))}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        if (x.sim) p.onSeleccionar(x.sim)
                      }
                    }}
                  />
                  </g>
                )
              })}
            </g>

            {/* Recorte festoneado: la banda p10–p90 alcanza el nivel vecino */}
            {p.modo === 'valor' && (
              <g className="recortes" filter="url(#alzado)" aria-hidden="true">
                {recortes.map((r) => (
                  <path key={r.i} d={r.d} className={`recorte nivel-${r.nivel}`} style={{ '--d': `${retraso(r.centro)}ms` } as CSSProperties} />
                ))}
              </g>
            )}

            {/* Leña: un disco por comuna con área proporcional a sus toneladas */}
            {p.modo === 'lena' && p.lena && (
              <g className="discos" filter="url(#alzado)" aria-hidden="true">
                {prep.map((x, i) => {
                  const c = p.lena!.comunas.find((q) => q.codigo === x.f.properties.codigo)
                  if (!c) return null
                  if (c.toneladas === null)
                    return <circle key={i} cx={x.centro[0]} cy={x.centro[1]} r={radioLena * 0.16} className="disco-sin-dato" />
                  const r = radioDisco(c.toneladas, tMaxLena, radioLena)
                  return r > 0 ? <circle key={i} cx={x.centro[0]} cy={x.centro[1]} r={r} className="disco" /> : null
                })}
              </g>
            )}

            {/* El agua: cauces con el ancho de su caudal y un brillo que corre aguas abajo; un punto por estación */}
            {p.modo === 'agua' && p.agua && (
              <g className="rios">
                {rios.map((x, i) => {
                  const w = anchoRio(caudalDeRio(x.r, p.agua!), x.r.clase)
                  return (
                    <g key={i} aria-hidden="true" className={`rio-${estadoDeRio(x.r, p.agua!)}`}>
                      <path d={x.d} className="rio-filo" style={{ strokeWidth: w + 2.4 }} />
                      <path d={x.d} className="rio" style={{ strokeWidth: w }} />
                      <path d={x.d} className="rio-flujo" style={{ strokeWidth: Math.max(0.7, w * 0.42) }} />
                    </g>
                  )
                })}
                {p.agua.estaciones.map((e) => {
                  const c = proj(e.lon, e.lat)
                  const elegida = e.codigo === p.agua!.elegida
                  const estado = estadoCaudal(p.agua!.fraccionDe(e))
                  return (
                    <circle
                      key={e.codigo}
                      cx={c[0]}
                      cy={c[1]}
                      r={(radioEstacion(e.medio) + (elegida ? 2 : 0)) / k}
                      className={`estacion agua-estado-${estado}${estado === 'critico' ? ' estacion-late' : ''}${elegida ? ' estacion-elegida' : ''}`}
                      role="button"
                      tabIndex={0}
                      aria-label={`${e.nombre}: ${e.medio} metros cúbicos por segundo`}
                      onPointerDown={(ev) => ev.stopPropagation()}
                      onClick={() => p.agua!.onElegir(e.codigo)}
                      onKeyDown={(ev) => {
                        if (ev.key === 'Enter' || ev.key === ' ') {
                          ev.preventDefault()
                          p.agua!.onElegir(e.codigo)
                        }
                      }}
                      onPointerMove={(ev) => {
                        ev.stopPropagation()
                        setSobreEstacion({ e, x: ev.clientX, y: ev.clientY })
                      }}
                      onPointerLeave={() => setSobreEstacion(null)}
                    />
                  )
                })}
              </g>
            )}

            {/* De dónde viene el aire: cintas de papel desde cada comuna de origen */}
            {sel && p.cintas.length > 0 && (
              <g className="cintas" aria-hidden="true">
                {p.cintas.map((c) => {
                  const o = porSim.get(c.desde)
                  if (!o) return null
                  const d = rutaCurva(o.centro, sel.centro)
                  const w = 2 + c.fraccion * 70
                  return (
                    <g key={c.desde}>
                      <path d={d} className="cinta-filo" style={{ strokeWidth: w + 3 }} />
                      <path d={d} className="cinta" style={{ strokeWidth: w }} />
                      <circle cx={o.centro[0]} cy={o.centro[1]} r={(w * 0.9) / k} className="cinta-nudo" />
                    </g>
                  )
                })}
              </g>
            )}

            {/* Comuna elegida: corte grueso de tinta y un leve alzado */}
            {sel && (
              <g className="elegida" aria-hidden="true" transform={`translate(${-1.5 / k} ${-1.5 / k})`}>
                <path d={sel.d} className="elegida-corte" />
              </g>
            )}
            {enfocado && <path d={enfocado.d} className="foco-corte" aria-hidden="true" />}
          </g>
        )}
      </svg>
      {sobreEstacion && p.agua && (
        <TarjetaMapa
          e={p.agua.etiqueta(sobreEstacion.e)}
          x={sobreEstacion.x - (caja.current?.getBoundingClientRect().left ?? 0)}
          y={sobreEstacion.y - (caja.current?.getBoundingClientRect().top ?? 0)}
          ancho={tam.w}
        />
      )}
      {!sobreEstacion && hov && tag && hover && (
        <TarjetaMapa
          e={tag}
          x={hover.x - (caja.current?.getBoundingClientRect().left ?? 0)}
          y={hover.y - (caja.current?.getBoundingClientRect().top ?? 0)}
          ancho={tam.w}
        />
      )}
      {p.children}
    </div>
  )
}
