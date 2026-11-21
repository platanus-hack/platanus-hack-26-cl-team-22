import { Map as MapaGL, type GeoJSONSource, type MapLayerMouseEvent, type StyleSpecification } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useMemo, useRef, useState } from 'react'
import { apilarNivel } from '../lib/capas'
import { claseFondo, variableDeClase } from '../lib/fondo'
import { radioDisco } from '../lib/lena'
import { poligonoMayor, proyectarGeometria, puntoInterior, type Pt } from '../lib/proyeccion'
import { aRgb, CAPAS, curva, estiloRelieve, mezclar, textoRgb, type RGB } from '../lib/relieve'
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
    const d = { modo: p.modo, cortes: p.cortes, puntos: p.puntos, difs: p.difs, difMax: p.difMax, mejor: p.mejor, lena: p.lena }
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
  }, [listo, prep, p.features, p.modo, p.cortes, p.puntos, p.difs, p.difMax, p.mejor, p.lena, p.reducido])

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
      {hover && tag && <TarjetaMapa e={tag} x={hover.x} y={hover.y} ancho={ancho} />}
      {p.children}
    </div>
  )
}
