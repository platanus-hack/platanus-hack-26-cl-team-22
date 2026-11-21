import { Map as MapaGL, setWorkerUrl, type GeoJSONSource, type MapLayerMouseEvent, type StyleSpecification } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
// MapLibre 6 ships its worker as a separate file and finds it with new URL(variable, import.meta.url),
// which Vite cannot see, so the file is missing in dev and in the build ("Worker failed to load") and
// the relief map never loads. Let Vite bundle the worker and tell MapLibre where it is.
import urlWorker from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
setWorkerUrl(urlWorker)
import { useEffect, useMemo, useRef, useState } from 'react'
import { anchoRio, caucesMedidos, estadoCaudal, factorAnio, fraccionNormal, radioEstacion, type EstadoCaudal, type Estacion } from '../lib/agua'
import { apilarNivel } from '../lib/capas'
import { claseFondo, variableDeClase } from '../lib/fondo'
import { radioDisco } from '../lib/lena'
import { poligonoMayor, proyectarGeometria, puntoInterior, type Pt } from '../lib/proyeccion'
import { anchoCauces, porCauce, aRgb, CAPAS, CAPAS_RIOS, curva, estiloRelieve, filtroCauces, mezclar, textoRgb, TRAZOS_FLUJO, type RGB } from '../lib/relieve'
import { esGranSantiago, limitesDe, type Limites } from '../lib/vista'
import type { PropsMapa } from './MapaPapel'
import { TarjetaMapa } from './Papel'

interface Props extends PropsMapa {
  /** estilo base ya leído (en línea o del paquete local) */
  estiloBase: unknown
  local: boolean
  /** el mapa no pudo arrancar: quien lo monta pasa al siguiente respaldo */
  onFalla: () => void
}

/** La ciudad se mira hacia la cordillera; la región, más desde arriba. `dz` corrige el zoom por la inclinación. */
const CAMARA = {
  'gran-santiago': { pitch: 60, bearing: 68, dz: 0.15 },
  region: { pitch: 40, bearing: 24, dz: 0.4 },
} as const
const DURACION_COLOR = 320
const ESPERA_CARGA_MS = 12_000
const RADIO_DISCO_M = 7000
/** cada cuánto avanza el brillo de los ríos y cuánto dura un latido de las estaciones */
const PASO_FLUJO_MS = 55
const LATIDO_MS = 2400
const DURACION_CAUDAL = 380
/** papel de cada estado del caudal: el del río y el del punto de su estación */
const PAPEL_ESTADO: Record<EstadoCaudal, string> = { sin: '--tinta-2', normal: '--agua', bajo: '--agua-baja', critico: '--agua-critica' }
/** cuánto se ve el brillo que corre: un río en estado crítico casi no corre */
const BRILLO_ESTADO: Record<EstadoCaudal, number> = { sin: 0.5, normal: 0.9, bajo: 0.55, critico: 0.18 }

type Datos = Parameters<GeoJSONSource['setData']>[0]
const fc = (features: unknown[]) => ({ type: 'FeatureCollection', features }) as unknown as Datos

function trama(): ImageData | null {
  const n = 16
  const lienzo = document.createElement('canvas')
  lienzo.width = lienzo.height = n
  const g = lienzo.getContext('2d')
  if (!g) return null
  g.strokeStyle = '#ffffff'
  g.lineWidth = 3
  for (const d of [-n, 0, n]) {
    g.beginPath()
    g.moveTo(d, n)
    g.lineTo(d + n, 0)
    g.stroke()
  }
  return g.getImageData(0, 0, n, n)
}

export default function MapaRelieve(p: Props) {
  const caja = useRef<HTMLDivElement>(null)
  const lienzo = useRef<HTMLDivElement>(null)
  const mapa = useRef<MapaGL | null>(null)
  const [listo, setListo] = useState(false)
  const [tam, setTam] = useState(0)
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null)
  const [sobreEstacion, setSobreEstacion] = useState<{ e: Estacion; x: number; y: number } | null>(null)
  const ultimo = useRef(p)
  ultimo.current = p

  const prep = useMemo(() => {
    const centros: (Pt | null)[] = []
    const comunas: unknown[] = []
    const rotulos: unknown[] = []
    const gs: Pt[] = []
    p.features.forEach((f, i) => {
      const mayor = poligonoMayor(proyectarGeometria(f.geometry, (x, y) => [x, y]))
      const c = mayor ? puntoInterior(mayor) : null
      centros.push(c)
      comunas.push({ type: 'Feature', id: i, properties: { i }, geometry: f.geometry })
      if (c) {
        rotulos.push({
          type: 'Feature',
          properties: { nombre: f.properties.nombre, orden: f.properties.simCodigo ? 0 : 1 },
          geometry: { type: 'Point', coordinates: c },
        })
        if (esGranSantiago(f.properties)) gs.push(c)
      }
    })
    const region: Limites = limitesDe(p.features) ?? [-71.7, -34.3, -69.7, -32.9]
    // Gran Santiago por los centros de sus comunas, con holgura: los polígonos completos llegan a la cordillera.
    const h = 0.06
    const granSantiago: Limites =
      gs.length >= 3
        ? [Math.min(...gs.map((q) => q[0])) - h, Math.min(...gs.map((q) => q[1])) - h, Math.max(...gs.map((q) => q[0])) + h, Math.max(...gs.map((q) => q[1])) + h]
        : region
    const porSim = new Map<string, number>()
    p.features.forEach((f, i) => {
      if (f.properties.simCodigo) porSim.set(f.properties.simCodigo, i)
    })
    return { centros, comunas: fc(comunas), rotulos: fc(rotulos), limites: { region, 'gran-santiago': granSantiago }, porSim }
  }, [p.features])

  // Arranque del mapa, una sola vez.
  useEffect(() => {
    const el = lienzo.current
    if (!el) return
    const cs = getComputedStyle(document.documentElement)
    const tok = (n: string, def: string) => cs.getPropertyValue(n).trim() || def
    let m: MapaGL
    try {
      const estilo = estiloRelieve(ultimo.current.estiloBase, {
        tinta: tok('--tinta', '#111111'),
        papel: tok('--papel', '#fafaf7'),
        disco: tok('--disco', '#ee7b22'),
        corte: tok('--corte', '#d9d9d0'),
        edificio: tok('--papel-2', '#e9e7df'),
        agua: tok('--agua', '#1f6fb2'),
        aguaClara: tok('--agua-clara', '#d7ecfa'),
      }) as unknown as StyleSpecification
      const cam = CAMARA[ultimo.current.encuadre]
      m = new MapaGL({
        container: el,
        style: estilo,
        center: [-70.66, -33.47],
        zoom: 9.4,
        pitch: cam.pitch,
        bearing: cam.bearing,
        maxPitch: 72,
        minZoom: 7,
        maxZoom: ultimo.current.local ? 13.5 : 16,
        attributionControl: { compact: true },
      })
    } catch (e) {
      console.warn('El mapa en relieve no pudo arrancar:', e)
      ultimo.current.onFalla()
      return
    }
    mapa.current = m
    const espera = window.setTimeout(() => {
      console.warn('El mapa en relieve no cargó a tiempo.')
      ultimo.current.onFalla()
    }, ESPERA_CARGA_MS)
    m.on('load', () => {
      window.clearTimeout(espera)
      const img = trama()
      if (img) {
        m.addImage('trama', img, { pixelRatio: 2 })
        m.addLayer(
          {
            id: CAPAS.trama,
            type: 'fill',
            source: 'comunas',
            paint: { 'fill-pattern': 'trama', 'fill-opacity': ['case', ['boolean', ['feature-state', 'cruce'], false], 0.5, 0] },
          },
          CAPAS.linea,
        )
      }
      setListo(true)
    })
    m.on('resize', () => setTam((n) => n + 1))
    // Una tesela que falla no es un error de la pantalla: el mapa sigue con lo que tiene.
    m.on('error', () => {})

    let sobre: number | null = null
    const marcar = (i: number | null) => {
      if (sobre === i) return
      if (sobre !== null) m.setFeatureState({ source: 'comunas', id: sobre }, { hover: false })
      sobre = i
      if (i !== null) m.setFeatureState({ source: 'comunas', id: i }, { hover: true })
    }
    const interactiva = (i: number) => ultimo.current.modo === 'lena' || !!ultimo.current.features[i]?.properties.simCodigo
    m.on('mousemove', CAPAS.relleno, (e: MapLayerMouseEvent) => {
      const i = e.features?.[0]?.id
      if (typeof i !== 'number') return
      marcar(interactiva(i) ? i : null)
      m.getCanvas().style.cursor = interactiva(i) ? 'pointer' : ''
      setHover({ i, x: e.point.x, y: e.point.y })
    })
    m.on('mouseleave', CAPAS.relleno, () => {
      marcar(null)
      m.getCanvas().style.cursor = ''
      setHover(null)
    })
    // Estaciones de caudal: se eligen con un clic y muestran su tarjeta al pasar.
    const estacionDe = (e: MapLayerMouseEvent) => {
      const codigo = e.features?.[0]?.properties?.codigo
      return typeof codigo === 'string' ? ultimo.current.agua?.porCodigo.get(codigo) : undefined
    }
    m.on('mousemove', CAPAS.estaciones, (e: MapLayerMouseEvent) => {
      const est = estacionDe(e)
      if (!est) return
      m.getCanvas().style.cursor = 'pointer'
      setSobreEstacion({ e: est, x: e.point.x, y: e.point.y })
    })
    m.on('mouseleave', CAPAS.estaciones, () => setSobreEstacion(null))
    m.on('click', CAPAS.estaciones, (e: MapLayerMouseEvent) => {
      const est = estacionDe(e)
      if (est) ultimo.current.agua?.onElegir(est.codigo)
    })
    m.on('click', CAPAS.relleno, (e: MapLayerMouseEvent) => {
      const i = e.features?.[0]?.id
      const sim = typeof i === 'number' ? ultimo.current.features[i]?.properties.simCodigo : undefined
      if (sim) ultimo.current.onSeleccionar(sim)
    })

    return () => {
      window.clearTimeout(espera)
      mapa.current = null
      m.remove()
    }
  }, [])

  // Polígonos y rótulos.
  useEffect(() => {
    const m = mapa.current
    if (!m || !listo) return
    ;(m.getSource('comunas') as GeoJSONSource | undefined)?.setData(prep.comunas)
    ;(m.getSource('rotulos') as GeoJSONSource | undefined)?.setData(prep.rotulos)
  }, [listo, prep])

  // Color de cada comuna: cambia en el mismo gesto que el dato, con una transición corta.
  const colores = useRef(new Map<number, RGB | null>())
  useEffect(() => {
    const m = mapa.current
    if (!m || !listo) return
    const cs = getComputedStyle(document.documentElement)
    const d = { modo: p.modo, cortes: p.cortes, puntos: p.puntos, difs: p.difs, difMax: p.difMax, mejor: p.mejor, lena: p.lena, pasa: p.agua?.pasa }
    const destino = p.features.map((f) => {
      const v = variableDeClase(claseFondo(d, f.properties.codigo, f.properties.simCodigo))
      const sim = f.properties.simCodigo
      return {
        color: v ? aRgb(cs.getPropertyValue(v)) : null,
        cruce: p.modo === 'valor' && !!sim && apilarNivel(p.puntos.get(sim), p.cortes).cruce !== null,
      }
    })
    const desde = destino.map((x, i) => colores.current.get(i) ?? x.color)
    const pintar = (t: number) => {
      destino.forEach((x, i) => {
        const a = desde[i]
        const c = x.color && a ? mezclar(a, x.color, t) : x.color
        colores.current.set(i, c)
        m.setFeatureState({ source: 'comunas', id: i }, { color: c ? textoRgb(c) : null, dato: c !== null, cruce: x.cruce })
      })
    }
    if (p.reducido || colores.current.size === 0) {
      pintar(1)
      return
    }
    const t0 = performance.now()
    let cuadro = requestAnimationFrame(function paso(ahora) {
      const t = Math.min(1, (ahora - t0) / DURACION_COLOR)
      pintar(1 - Math.pow(1 - t, 3))
      if (t < 1) cuadro = requestAnimationFrame(paso)
    })
    return () => cancelAnimationFrame(cuadro)
  }, [listo, prep, p.features, p.modo, p.cortes, p.puntos, p.difs, p.difMax, p.mejor, p.lena, p.agua?.pasa, p.reducido])

  // Comuna elegida.
  const elegida = useRef<number | null>(null)
  useEffect(() => {
    const m = mapa.current
    if (!m || !listo) return
    const i = p.seleccionada ? (prep.porSim.get(p.seleccionada) ?? null) : null
    if (elegida.current !== null) m.setFeatureState({ source: 'comunas', id: elegida.current }, { sel: false })
    elegida.current = i
    if (i !== null) m.setFeatureState({ source: 'comunas', id: i }, { sel: true })
  }, [listo, prep, p.seleccionada])

  // De dónde viene el aire: cintas desde cada comuna de origen.
  useEffect(() => {
    const m = mapa.current
    if (!m || !listo) return
    const iSel = p.seleccionada ? prep.porSim.get(p.seleccionada) : undefined
    const fin = iSel !== undefined ? prep.centros[iSel] : null
    const lineas: unknown[] = []
    if (fin)
      for (const c of p.cintas) {
        const io = prep.porSim.get(c.desde)
        const ini = io !== undefined ? prep.centros[io] : null
        if (!ini) continue
        lineas.push({ type: 'Feature', properties: { ancho: 2 + c.fraccion * 46 }, geometry: { type: 'LineString', coordinates: curva(ini, fin) } })
      }
    ;(m.getSource('cintas') as GeoJSONSource | undefined)?.setData(fc(lineas))
  }, [listo, prep, p.cintas, p.seleccionada])

  // Leña: un disco por comuna con área proporcional a sus toneladas.
  useEffect(() => {
    const m = mapa.current
    if (!m || !listo) return
    const discos: unknown[] = []
    if (p.modo === 'lena' && p.lena) {
      const tMax = Math.max(0, ...p.lena.comunas.map((c) => c.toneladas ?? 0))
      p.features.forEach((f, i) => {
        const centro = prep.centros[i]
        const c = p.lena!.comunas.find((q) => q.codigo === f.properties.codigo)
        if (!centro || !c) return
        const r = c.toneladas === null ? RADIO_DISCO_M * 0.16 : radioDisco(c.toneladas, tMax, RADIO_DISCO_M)
        if (r > 0) discos.push({ type: 'Feature', properties: { r, dato: c.toneladas !== null }, geometry: { type: 'Point', coordinates: centro } })
      })
    }
    ;(m.getSource('discos') as GeoJSONSource | undefined)?.setData(fc(discos))
  }, [listo, prep, p.features, p.modo, p.lena])

  // El agua: los cauces son los de las teselas. Se encienden con el modo, se filtran por nombre y su ancho
  // sigue al caudal del año mostrado, con una transición corta.
  const aguaActiva = p.modo === 'agua' ? p.agua : null
  const cauces = useMemo(() => (aguaActiva ? caucesMedidos(aguaActiva.estaciones, aguaActiva.cauces) : []), [aguaActiva?.estaciones, aguaActiva?.cauces])
  const anchos = useRef<number[]>([])
  useEffect(() => {
    const m = mapa.current
    if (!m || !listo) return
    const hay = !!aguaActiva
    for (const id of CAPAS_RIOS) if (m.getLayer(id)) m.setLayoutProperty(id, 'visibility', hay ? 'visible' : 'none')
    if (!aguaActiva) {
      anchos.current = []
      return
    }
    const nombrados = (w: number[]) => cauces.map((c, i) => ({ nombres: c.nombres, ancho: w[i]! }))
    const filtro = filtroCauces(nombrados(cauces.map(() => 1)), prep.limites.region) as Parameters<MapaGL['setFilter']>[1]
    for (const id of [CAPAS.riosFilo, CAPAS.rios, CAPAS.flujo]) if (m.getLayer(id)) m.setFilter(id, filtro)
    const destino = cauces.map((c) => anchoRio(c.estacion.medio * factorAnio(c.estacion, aguaActiva.anio), 'river'))
    // Color y brillo según el estado del caudal de cada río en lo que se mira.
    const cs = getComputedStyle(document.documentElement)
    const estados = cauces.map((c) => estadoCaudal(fraccionNormal(c.estacion, aguaActiva.anio)))
    const color = porCauce(cauces.map((c, i) => ({ nombres: c.nombres, valor: cs.getPropertyValue(PAPEL_ESTADO[estados[i]!]).trim() || '#1f6fb2' })), cs.getPropertyValue('--agua').trim() || '#1f6fb2')
    const brillo = porCauce(cauces.map((c, i) => ({ nombres: c.nombres, valor: BRILLO_ESTADO[estados[i]!] })), 0.9)
    if (m.getLayer(CAPAS.rios)) m.setPaintProperty(CAPAS.rios, 'line-color', color as string)
    if (m.getLayer(CAPAS.flujo)) m.setPaintProperty(CAPAS.flujo, 'line-opacity', brillo as number)
    const desde = anchos.current.length === destino.length ? [...anchos.current] : destino
    type Ancho = number // la expresión se arma en relieve.ts sin los tipos de MapLibre
    const poner = (t: number) => {
      const w = destino.map((d, i) => desde[i]! + (d - desde[i]!) * t)
      anchos.current = w
      const c = nombrados(w)
      if (m.getLayer(CAPAS.riosFilo)) m.setPaintProperty(CAPAS.riosFilo, 'line-width', anchoCauces(c, 1, 2.4) as unknown as Ancho)
      if (m.getLayer(CAPAS.rios)) m.setPaintProperty(CAPAS.rios, 'line-width', anchoCauces(c) as unknown as Ancho)
      if (m.getLayer(CAPAS.flujo)) m.setPaintProperty(CAPAS.flujo, 'line-width', anchoCauces(c, 0.42, 0, 0.7) as unknown as Ancho)
    }
    if (p.reducido || desde === destino) {
      poner(1)
      return
    }
    const t0 = performance.now()
    let cuadro = requestAnimationFrame(function paso(ahora) {
      const t = Math.min(1, (ahora - t0) / DURACION_CAUDAL)
      poner(1 - Math.pow(1 - t, 3))
      if (t < 1) cuadro = requestAnimationFrame(paso)
    })
    return () => cancelAnimationFrame(cuadro)
  }, [listo, aguaActiva, cauces, aguaActiva?.anio, prep.limites.region, p.reducido])

  // Estaciones: un punto por estación, del color de su caída en la megasequía.
  useEffect(() => {
    const m = mapa.current
    if (!m || !listo) return
    const cs = getComputedStyle(document.documentElement)
    const puntos = aguaActiva
      ? aguaActiva.estaciones.map((e) => {
          const estado = estadoCaudal(fraccionNormal(e, aguaActiva.anio))
          return {
            type: 'Feature',
            properties: {
              codigo: e.codigo,
              r: radioEstacion(e.medio),
              color: cs.getPropertyValue(PAPEL_ESTADO[estado]).trim() || '#1f6fb2',
              sel: e.codigo === aguaActiva.elegida,
              late: estado === 'critico',
            },
            geometry: { type: 'Point', coordinates: [e.lon, e.lat] },
          }
        })
      : []
    ;(m.getSource('estaciones') as GeoJSONSource | undefined)?.setData(fc(puntos))
    if (!aguaActiva) setSobreEstacion(null)
  }, [listo, aguaActiva, aguaActiva?.estaciones, aguaActiva?.elegida, aguaActiva?.anio])

  // Movimiento del agua: el brillo corre aguas abajo y las estaciones laten. Quieto si se pidió menos movimiento.
  const hayAgua = !!aguaActiva
  useEffect(() => {
    const m = mapa.current
    if (!m || !listo || !hayAgua || p.reducido) return
    let pasoPrevio = -1
    let cuadro = requestAnimationFrame(function anima(ahora) {
      const paso = Math.floor(ahora / PASO_FLUJO_MS) % TRAZOS_FLUJO.length
      if (paso !== pasoPrevio) {
        for (const id of [CAPAS.flujoBase, CAPAS.flujo]) if (m.getLayer(id)) m.setPaintProperty(id, 'line-dasharray', TRAZOS_FLUJO[paso] as number[])
        pasoPrevio = paso
      }
      if (m.getLayer(CAPAS.pulso)) {
        const t = (ahora % LATIDO_MS) / LATIDO_MS
        m.setPaintProperty(CAPAS.pulso, 'circle-radius', ['*', ['get', 'r'], 1 + t * 2.2])
        m.setPaintProperty(CAPAS.pulso, 'circle-opacity', 0.45 * (1 - t))
      }
      cuadro = requestAnimationFrame(anima)
    })
    return () => {
      cancelAnimationFrame(cuadro)
      if (m.getLayer(CAPAS.pulso)) m.setPaintProperty(CAPAS.pulso, 'circle-opacity', 0)
    }
  }, [listo, hayAgua, p.reducido])

  // Encuadre: Gran Santiago o toda la región; `reencuadre` fuerza volver aunque no cambie.
  const encuadrado = useRef(false)
  const tamPrevio = useRef(0)
  useEffect(() => {
    const m = mapa.current
    if (!m || !listo) return
    const lim = prep.limites[p.encuadre]
    const cam = CAMARA[p.encuadre]
    const leyenda = caja.current?.querySelector('.leyenda')?.getBoundingClientRect().height ?? 0
    const controles = caja.current?.querySelector('.controles-mapa')?.getBoundingClientRect().height ?? 0
    const c = m.cameraForBounds(
      [
        [lim[0], lim[1]],
        [lim[2], lim[3]],
      ],
      { bearing: cam.bearing, padding: { top: controles + 30, bottom: leyenda * 0.45 + 20, left: 24, right: 24 } },
    )
    if (!c || c.zoom === undefined || !c.center) return
    const destino = { center: c.center, zoom: c.zoom + cam.dz, bearing: cam.bearing, pitch: cam.pitch }
    // Al cambiar el tamaño de la pantalla se reencuadra sin animación.
    if (!encuadrado.current || p.reducido || tamPrevio.current !== tam) m.jumpTo(destino)
    else m.easeTo({ ...destino, duration: 1100 })
    encuadrado.current = true
    tamPrevio.current = tam
  }, [listo, prep, p.encuadre, p.reencuadre, p.reducido, tam])

  const hov = hover ? p.features[hover.i] : undefined
  const tag = hov ? p.etiqueta(hov) : null
  const ancho = caja.current?.getBoundingClientRect().width ?? 0

  return (
    <div className="mapa mapa-relieve" ref={caja}>
      <div className="mapa-gl" ref={lienzo} role="application" aria-label="Mapa en relieve de las comunas de la Región Metropolitana" />
      {sobreEstacion && p.agua && <TarjetaMapa e={p.agua.etiqueta(sobreEstacion.e)} x={sobreEstacion.x} y={sobreEstacion.y} ancho={ancho} />}
      {!sobreEstacion && hover && tag && <TarjetaMapa e={tag} x={hover.x} y={hover.y} ancho={ancho} />}
      {p.children}
    </div>
  )
}
