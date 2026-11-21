import { useEffect, useMemo, useRef, useState } from 'react'
import { DeckGL } from '@deck.gl/react'
import { FlyToInterpolator, MapView, type PickingInfo } from '@deck.gl/core'
import { ArcLayer, GeoJsonLayer, PathLayer } from '@deck.gl/layers'
import { clase, hexARgb, leerToken, type RGB } from '../lib/color'
import { claseDiferencia, type Diferencia } from '../lib/diferencia'
import type { GeoFeature } from '../lib/geo'
import type { Punto } from '../lib/data'
import type { Mejor } from '../lib/types'
import { ajustarLimites, type Limites, type LimitesDeVista, type Relleno } from '../lib/vista'

export type Encuadre = 'gran-santiago' | 'region'

export interface Arco {
  desde: [number, number]
  hasta: [number, number]
  hogares: number
}

/** Línea del origen del aire hacia la comuna seleccionada; el ancho sale de `fraccion`. */
export interface LineaOrigen {
  desde: [number, number]
  hasta: [number, number]
  fraccion: number
}

export interface HoverInfo {
  x: number
  y: number
  codigo: string | null
  nombre: string
}

/** Modo diferencia: color y altura salen de (escenario activo − escenario de referencia). */
export interface ModoDiferencia {
  valores: ReadonlyMap<string, Diferencia>
  /** la escala simétrica va de −max a +max */
  max: number
  /** 5 colores; el índice 0 es la mayor mejora y el 4 el mayor empeoramiento */
  paleta: string[]
}

interface Props {
  features: GeoFeature[]
  /** punto (p10, p50, p90) por código del JSON, para el año y escenario vigentes */
  puntos: ReadonlyMap<string, Punto>
  dominio: [number, number]
  mejor: Mejor
  rampa: string[]
  diferencia: ModoDiferencia | null
  seleccionada: string | null
  arcos: Arco[]
  origenes: LineaOrigen[]
  /** metros de altura por unidad de la variable (o de la diferencia, en modo diferencia) */
  escalaAltura: number
  limites: LimitesDeVista | null
  encuadre: Encuadre
  /** sube cada vez que se pide "Restablecer vista" */
  reinicio: number
  onSeleccionar: (codigo: string | null) => void
  onHover: (h: HoverInfo | null) => void
}

const VISTA = new MapView({ repeat: false })
const VUELO = new FlyToInterpolator({ speed: 1.4 })

const PITCH = 38
/** Cuánto se puede alejar respecto del encuadre de toda la región, y cuánto acercar. */
const ALEJAR_MAX = 0.6
const ACERCAR_MAX = 12
const MARGEN_PX = 24
/** Con el mapa inclinado, lo cercano a la cámara se ve más ancho: un poco de zoom de menos para que no se corte. */
const HOLGURA_INCLINACION = 0.2
const ANCHO_LINEA_ORIGEN_PX = 90

/** Respaldo si no hay geometría alguna: la región completa. */
const LIMITES_REGION: Limites = [-71.7, -34.3, -69.8, -32.9]

function px(token: string, respaldo: number): number {
  const n = parseFloat(leerToken(token, `${respaldo}px`))
  return Number.isFinite(n) ? n : respaldo
}

/** Lo que tapan los paneles laterales, el de arriba y el de abajo, más un margen. */
function leerRelleno(): Relleno {
  return {
    izq: px('--ancho-izq', 300) + MARGEN_PX,
    der: px('--ancho-der', 340) + MARGEN_PX,
    sup: px('--alto-sup', 76) + MARGEN_PX,
    inf: px('--alto-inf', 84) + MARGEN_PX,
  }
}

export function MapaComunas(p: Props) {
  const { limites, encuadre, reinicio } = p

  const vistaPara = (enc: Encuadre, animar: boolean) => {
    const ancho = window.innerWidth
    const alto = window.innerHeight
    const relleno = leerRelleno()
    const lim = limites ?? { region: LIMITES_REGION, granSantiago: LIMITES_REGION }
    const region = ajustarLimites(lim.region, ancho, alto, relleno)
    const minZoom = region.zoom - HOLGURA_INCLINACION - ALEJAR_MAX
    const fit = ajustarLimites(enc === 'region' ? lim.region : lim.granSantiago, ancho, alto, relleno, {
      minZoom: 0,
      maxZoom: ACERCAR_MAX,
    })
    return {
      ...fit,
      zoom: Math.max(minZoom, fit.zoom - HOLGURA_INCLINACION),
      pitch: PITCH,
      bearing: 0,
      minZoom,
      maxZoom: ACERCAR_MAX,
      ...(animar ? { transitionDuration: 900, transitionInterpolator: VUELO } : {}),
    }
  }

  const [vista, setVista] = useState(() => vistaPara(encuadre, false))

  // Cambiar de encuadre o restablecer: se anima hasta el ajuste calculado desde los polígonos.
  const primera = useRef(true)
  useEffect(() => {
    if (primera.current) {
      primera.current = false
      return
    }
    setVista(vistaPara(encuadre, true))
    // vistaPara solo depende de props que ya están en la lista de dependencias
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [encuadre, reinicio])

  const colores = useMemo(() => {
    return {
      rampa: p.rampa.map(hexARgb),
      div: (p.diferencia?.paleta ?? []).map(hexARgb),
      sinDato: hexARgb(leerToken('--sin-dato', '#bdb9ae')),
      acento: hexARgb(leerToken('--acento', '#1f5c63')),
      tinta: hexARgb(leerToken('--tinta', '#1b1b19')),
      tinta3: hexARgb(leerToken('--tinta-3', '#77746b')),
    }
  }, [p.rampa, p.diferencia?.paleta])

  const { puntos, dominio, mejor, diferencia, seleccionada, escalaAltura, onHover, onSeleccionar } = p

  const capas = useMemo(() => {
    const cod = (f: GeoFeature) => f.properties.simCodigo
    const pt = (f: GeoFeature) => {
      const c = cod(f)
      return c ? puntos.get(c) : undefined
    }
    const dif = (f: GeoFeature) => {
      const c = cod(f)
      return c && diferencia ? diferencia.valores.get(c) : undefined
    }
    /** Altura en unidades de la variable: el valor, o la magnitud de la diferencia. */
    const altura = (f: GeoFeature) => (diferencia ? Math.abs(dif(f)?.delta ?? 0) : (pt(f)?.p50 ?? 0))

    const poligonos = new GeoJsonLayer<GeoFeature['properties']>({
      id: 'comunas',
      data: p.features as never,
      pickable: true,
      filled: true,
      stroked: true,
      extruded: true,
      wireframe: false,
      lineWidthUnits: 'pixels',
      elevationScale: escalaAltura,
      material: { ambient: 0.72, diffuse: 0.55, shininess: 4, specularColor: [20, 20, 20] },
      getElevation: (f: unknown) => altura(f as GeoFeature),
      getFillColor: (f: unknown): [number, number, number, number] => {
        const feat = f as GeoFeature
        let c: RGB = colores.sinDato
        if (diferencia) {
          const d = dif(feat)
          if (d) c = colores.div[claseDiferencia(d.delta, diferencia.max, mejor)] ?? colores.sinDato
        } else {
          const v = pt(feat)
          if (v) c = colores.rampa[clase(v.p50, dominio, mejor)]!
        }
        return [c[0], c[1], c[2], 255]
      },
      getLineColor: [...colores.tinta, 110],
      getLineWidth: 0.8,
      updateTriggers: {
        getElevation: [puntos, diferencia],
        getFillColor: [puntos, dominio, mejor, colores, diferencia],
      },
      onHover: (info: PickingInfo) => {
        const f = info.object as GeoFeature | undefined
        if (!f) return onHover(null)
        onHover({ x: info.x, y: info.y, codigo: f.properties.simCodigo ?? null, nombre: f.properties.nombre })
      },
      onClick: (info: PickingInfo) => {
        const f = info.object as GeoFeature | undefined
        const c = f?.properties.simCodigo
        onSeleccionar(c ?? null)
      },
    })

    // El contorno de una capa extruida se dibuja a nivel del suelo; la seleccionada se perfila en su cima.
    const anillos: { path: [number, number, number][] }[] = []
    const sel = p.features.find((f) => f.properties.simCodigo !== undefined && f.properties.simCodigo === seleccionada)
    if (sel) {
      const h = altura(sel) * escalaAltura + 60
      const polis = sel.geometry.type === 'Polygon' ? [sel.geometry.coordinates as number[][][]] : (sel.geometry.coordinates as number[][][][])
      for (const poly of polis) for (const ring of poly) anillos.push({ path: ring.map(([x, y]) => [x!, y!, h] as [number, number, number]) })
    }
    const contorno = new PathLayer<{ path: [number, number, number][] }>({
      id: 'seleccion',
      data: anillos,
      getPath: (d) => d.path,
      getColor: [...colores.acento, 255],
      getWidth: 3.5,
      widthUnits: 'pixels',
      parameters: { depthCompare: 'always' },
    })

    const flujos = new ArcLayer<Arco>({
      id: 'flujos',
      data: p.arcos,
      getSourcePosition: (d) => d.desde,
      getTargetPosition: (d) => d.hasta,
      getSourceColor: [...colores.tinta3, 200],
      getTargetColor: [...colores.tinta, 255],
      getWidth: (d) => 1 + Math.sqrt(d.hogares) / 6,
      widthUnits: 'pixels',
      getHeight: 0.6,
    })

    // Origen del aire: una línea por comuna de origen, con ancho proporcional a su parte.
    const origen = new ArcLayer<LineaOrigen>({
      id: 'origen-aire',
      data: p.origenes,
      getSourcePosition: (d) => d.desde,
      getTargetPosition: (d) => d.hasta,
      getSourceColor: [...colores.acento, 120],
      getTargetColor: [...colores.acento, 255],
      getWidth: (d) => d.fraccion * ANCHO_LINEA_ORIGEN_PX,
      widthUnits: 'pixels',
      widthMinPixels: 2,
      getHeight: 0.5,
      parameters: { depthCompare: 'always' },
    })

    const lista = [poligonos, contorno]
    if (p.arcos.length > 0) lista.push(flujos as never)
    if (p.origenes.length > 0) lista.push(origen as never)
    return lista
  }, [p.features, p.arcos, p.origenes, puntos, dominio, mejor, diferencia, seleccionada, escalaAltura, colores, onHover, onSeleccionar])

  return (
    <DeckGL
      views={VISTA}
      initialViewState={vista}
      controller={{ dragRotate: true, touchRotate: false }}
      layers={capas}
      onClick={(info) => {
        if (!info.object) onSeleccionar(null)
      }}
      getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
      style={{ position: 'absolute', inset: '0' }}
    />
  )
}
