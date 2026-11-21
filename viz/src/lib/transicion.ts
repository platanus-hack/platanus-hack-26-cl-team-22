/**
 * Primitivas puras de transición espacio-temporal para el mapa.
 * Prepara interpolación de bandas, curvas con respeto a prefers-reduced-motion,
 * lectura de focos y features GeoJSON sin implementar todavía bucles de animación en UI.
 */

import type { Punto } from './data'
import type { DireccionCambio, TransformacionEscenario } from './types'

export type ModoTransicion = 'ninguno' | 'coropleta_continua' | 'focos' | 'encuadre_guiado'
export type CurvaTransicion = 'lineal' | 'ease-out-cubic' | 'ease-out-expo'

export interface OpcionesTransicion {
  modo: ModoTransicion
  duracionMs: number
  reducido: boolean
  curva: CurvaTransicion
  umbralFoco: number
}

export interface CursorTiempo {
  indiceBase: number
  indiceSiguiente: number
  fraccion: number
}

export interface EstadoFocoComuna {
  codigo: string
  direccion: DireccionCambio
  deltaP50: number
  incertidumbre: number
  intensidad: number
}

export interface EstadoTransicionMapa {
  activo: boolean
  modo: ModoTransicion
  referencia: string | null
  variable: string | null
  tipo: string | null
  cursor: CursorTiempo
  intensidadRegional: number
  epicentro: { lat: number; lon: number } | null
  bbox: [number, number, number, number] | null
  focos: EstadoFocoComuna[]
}

export interface FeatureFocoGeo {
  type: 'Feature'
  properties: {
    codigo: string
    direccion: DireccionCambio
    deltaP50: number
    incertidumbre: number
    intensidad: number
  }
  geometry: {
    type: 'Point'
    coordinates: [number, number]
  }
}

export const OPCIONES_TRANSICION_DEFECTO: Readonly<OpcionesTransicion> = {
  modo: 'ninguno',
  duracionMs: 420,
  reducido: false,
  curva: 'ease-out-cubic',
  umbralFoco: 0.15,
}

const acotar01 = (t: number): number => {
  if (!Number.isFinite(t)) return 0
  return Math.min(1, Math.max(0, t))
}

export function lineal(t: number): number {
  return acotar01(t)
}

export function easeOutCubic(t: number): number {
  const x = acotar01(t)
  return 1 - Math.pow(1 - x, 3)
}

export function easeOutExpo(t: number): number {
  const x = acotar01(t)
  return x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)
}

/** Devuelve el avance normalizado [0, 1]; si `reducido` es true salta directo a 1. */
export function resolverProgreso(
  t: number,
  reducido: boolean,
  curva: CurvaTransicion = 'ease-out-cubic',
): number {
  if (reducido) return 1
  if (curva === 'lineal') return lineal(t)
  if (curva === 'ease-out-expo') return easeOutExpo(t)
  return easeOutCubic(t)
}

/** Convierte un progreso continuo [0, nAnios - 1] en índices enteros + fracción [0, 1). */
export function cursorDeProgreso(progreso: number, nAnios: number): CursorTiempo {
  if (nAnios <= 0) return { indiceBase: 0, indiceSiguiente: 0, fraccion: 0 }
  const maxIdx = nAnios - 1
  const p = Number.isFinite(progreso) ? Math.min(maxIdx, Math.max(0, progreso)) : 0
  const indiceBase = Math.floor(p)
  const indiceSiguiente = Math.min(maxIdx, indiceBase + 1)
  const fraccion = indiceBase === indiceSiguiente ? 0 : p - indiceBase
  return { indiceBase, indiceSiguiente, fraccion }
}

/** Interpola linealmente una banda (p10, p50, p90) manteniendo el orden estadístico. */
export function interpolarBanda(a: Punto, b: Punto, t: number): Punto {
  const k = acotar01(t)
  return {
    p10: a.p10 + (b.p10 - a.p10) * k,
    p50: a.p50 + (b.p50 - a.p50) * k,
    p90: a.p90 + (b.p90 - a.p90) * k,
  }
}

/** Interpola un mapa de bandas por comuna entre dos instantes o escenarios. */
export function interpolarMapaPuntos(
  desde: ReadonlyMap<string, Punto>,
  hasta: ReadonlyMap<string, Punto>,
  t: number,
  opciones: { reducido?: boolean; curva?: CurvaTransicion } = {},
): Map<string, Punto> {
  const k = resolverProgreso(t, opciones.reducido ?? false, opciones.curva ?? 'ease-out-cubic')
  const out = new Map<string, Punto>()
  for (const [codigo, destino] of hasta) {
    const origen = desde.get(codigo)
    out.set(codigo, origen ? interpolarBanda(origen, destino, k) : destino)
  }
  return out
}

const interpolarSerie = (serie: readonly number[], cursor: CursorTiempo): number => {
  const a = serie[cursor.indiceBase] ?? serie[0] ?? 0
  const b = serie[cursor.indiceSiguiente] ?? a
  return a + (b - a) * acotar01(cursor.fraccion)
}

/** Calcula el estado de focos e intensidad regional de una transformación en el cursor dado. */
export function estadoTransformacionEnCursor(
  tr: TransformacionEscenario | undefined,
  cursor: CursorTiempo,
  opciones: Partial<OpcionesTransicion> = {},
): EstadoTransicionMapa {
  const opts: OpcionesTransicion = { ...OPCIONES_TRANSICION_DEFECTO, ...opciones }
  if (!tr) {
    return {
      activo: false,
      modo: opts.modo,
      referencia: null,
      variable: null,
      tipo: null,
      cursor,
      intensidadRegional: 0,
      epicentro: null,
      bbox: null,
      focos: [],
    }
  }

  const intensidadRegional = acotar01(interpolarSerie(tr.intensidad_regional, cursor))
  const focos: EstadoFocoComuna[] = []
  for (const c of tr.comunas_foco) {
    const intensidad = acotar01(interpolarSerie(c.intensidad, cursor))
    if (intensidad < opts.umbralFoco) continue
    focos.push({
      codigo: c.codigo,
      direccion: c.direccion,
      deltaP50: interpolarSerie(c.delta_p50, cursor),
      incertidumbre: Math.max(0, interpolarSerie(c.incertidumbre, cursor)),
      intensidad,
    })
  }
  focos.sort(
    (a, b) =>
      b.intensidad - a.intensidad ||
      Math.abs(b.deltaP50) - Math.abs(a.deltaP50) ||
      a.codigo.localeCompare(b.codigo),
  )

  return {
    activo: opts.modo !== 'ninguno' && (focos.length > 0 || intensidadRegional > 0),
    modo: opts.modo,
    referencia: tr.referencia,
    variable: tr.variable,
    tipo: tr.tipo,
    cursor,
    intensidadRegional,
    epicentro: tr.epicentro,
    bbox: tr.bbox,
    focos,
  }
}

/** Devuelve las N comunas con mayor transformación en el estado actual. */
export function comunasMasTransformadas(
  estado: EstadoTransicionMapa,
  limite = 5,
): EstadoFocoComuna[] {
  if (limite <= 0) return []
  return [...estado.focos]
    .sort(
      (a, b) =>
        b.intensidad - a.intensidad ||
        Math.abs(b.deltaP50) - Math.abs(a.deltaP50) ||
        a.codigo.localeCompare(b.codigo),
    )
    .slice(0, limite)
}

/** Prepara features GeoJSON puntuales para futuras capas de focos o halos sin dibujarlas todavía. */
export function featuresDeFocos(
  estado: EstadoTransicionMapa,
  centrosPorComuna: ReadonlyMap<string, readonly [number, number]>,
): FeatureFocoGeo[] {
  const features: FeatureFocoGeo[] = []
  for (const f of estado.focos) {
    const centro = centrosPorComuna.get(f.codigo)
    if (!centro) continue
    features.push({
      type: 'Feature',
      properties: {
        codigo: f.codigo,
        direccion: f.direccion,
        deltaP50: f.deltaP50,
        incertidumbre: f.incertidumbre,
        intensidad: f.intensidad,
      },
      geometry: {
        type: 'Point',
        coordinates: [centro[0], centro[1]],
      },
    })
  }
  return features
}
