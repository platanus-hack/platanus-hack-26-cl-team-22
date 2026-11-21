import type { GeoFeature } from './geo'

/** [lonMin, latMin, lonMax, latMax] */
export type Limites = [number, number, number, number]

export interface Relleno {
  izq: number
  der: number
  sup: number
  inf: number
}

export interface Encuadre {
  longitude: number
  latitude: number
  zoom: number
}

/** Gran Santiago: las 32 comunas de la provincia de Santiago, más Puente Alto y San Bernardo. */
const EXTRA_GRAN_SANTIAGO = new Set(['13201', '13401'])

export function esGranSantiago(p: { codigo: string; provincia?: string }): boolean {
  return p.provincia === 'Santiago' || EXTRA_GRAN_SANTIAGO.has(p.codigo)
}

/** Recorre cualquier anidación de coordenadas GeoJSON y junta los extremos. */
export function limitesDeCoordenadas(coords: unknown, acc: Limites = [Infinity, Infinity, -Infinity, -Infinity]): Limites {
  if (!Array.isArray(coords)) return acc
  if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
    const x = coords[0]
    const y = coords[1]
    if (Number.isFinite(x) && Number.isFinite(y)) {
      acc[0] = Math.min(acc[0], x)
      acc[1] = Math.min(acc[1], y)
      acc[2] = Math.max(acc[2], x)
      acc[3] = Math.max(acc[3], y)
    }
    return acc
  }
  for (const c of coords) limitesDeCoordenadas(c, acc)
  return acc
}

/** Límites de un conjunto de features; null si no hay ninguna coordenada válida. */
export function limitesDe(features: readonly GeoFeature[]): Limites | null {
  const acc: Limites = [Infinity, Infinity, -Infinity, -Infinity]
  for (const f of features) limitesDeCoordenadas(f.geometry.coordinates, acc)
  return Number.isFinite(acc[0]) && acc[2] >= acc[0] && acc[3] >= acc[1] ? acc : null
}

export interface LimitesDeVista {
  region: Limites
  granSantiago: Limites
}

/** Límites de toda la región y del Gran Santiago, calculados desde los polígonos. */
export function limitesDeVista(features: readonly GeoFeature[]): LimitesDeVista | null {
  const region = limitesDe(features)
  if (!region) return null
  const gs = limitesDe(features.filter((f) => esGranSantiago(f.properties)))
  return { region, granSantiago: gs ?? region }
}

const TAM_TESELA = 512

const mercX = (lon: number) => (lon + 180) / 360
const mercY = (lat: number) => {
  const s = Math.sin((Math.max(-85, Math.min(85, lat)) * Math.PI) / 180)
  return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)
}
const lonDeX = (x: number) => x * 360 - 180
const latDeY = (y: number) => (Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180) / Math.PI

/**
 * Centro y zoom (Web Mercator, teselas de 512 px) para que los límites calcen
 * en el área libre de la pantalla, descontando lo que tapan los paneles.
 * El centro de la vista se corre para que los límites queden al medio del área libre.
 */
export function ajustarLimites(
  lim: Limites,
  ancho: number,
  alto: number,
  relleno: Relleno,
  topes: { minZoom?: number; maxZoom?: number } = {},
): Encuadre {
  const libreX = Math.max(50, ancho - relleno.izq - relleno.der)
  const libreY = Math.max(50, alto - relleno.sup - relleno.inf)
  const x0 = mercX(lim[0])
  const x1 = mercX(lim[2])
  const yTop = mercY(lim[3])
  const yBot = mercY(lim[1])
  const dx = Math.max(1e-9, x1 - x0)
  const dy = Math.max(1e-9, yBot - yTop)
  let zoom = Math.log2(Math.min(libreX / (dx * TAM_TESELA), libreY / (dy * TAM_TESELA)))
  zoom = Math.min(topes.maxZoom ?? 20, Math.max(topes.minZoom ?? 0, zoom))
  const mundo = TAM_TESELA * 2 ** zoom
  const cx = (x0 + x1) / 2 - (relleno.izq - relleno.der) / 2 / mundo
  const cy = (yTop + yBot) / 2 - (relleno.sup - relleno.inf) / 2 / mundo
  return { longitude: lonDeX(cx), latitude: latDeY(cy), zoom }
}
