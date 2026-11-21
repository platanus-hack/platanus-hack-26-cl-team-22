import { slug } from './format'
import type { Comuna } from './types'

export interface GeoProps {
  codigo: string
  nombre: string
  provincia?: string
  /** código de la comuna en el JSON de simulación, si se logró emparejar */
  simCodigo?: string
}

export interface GeoFeature {
  type: 'Feature'
  properties: GeoProps
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: unknown }
}

export interface GeoCollection {
  type: 'FeatureCollection'
  features: GeoFeature[]
}

const esObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null

/** Extrae solo las features válidas (polígonos con codigo y nombre de texto). */
export function leerFeatures(raw: unknown): GeoFeature[] {
  if (!esObj(raw) || !Array.isArray(raw.features)) return []
  const out: GeoFeature[] = []
  for (const f of raw.features) {
    if (!esObj(f) || !esObj(f.properties) || !esObj(f.geometry)) continue
    const p = f.properties
    const g = f.geometry
    if (typeof p.nombre !== 'string') continue
    if (g.type !== 'Polygon' && g.type !== 'MultiPolygon') continue
    out.push({
      type: 'Feature',
      properties: {
        codigo: String(p.codigo ?? ''),
        nombre: p.nombre,
        provincia: typeof p.provincia === 'string' ? p.provincia : undefined,
      },
      geometry: { type: g.type, coordinates: g.coordinates },
    })
  }
  return out
}

/**
 * Empareja cada comuna del JSON con un polígono: primero por código exacto,
 * si no por nombre sin tildes ni mayúsculas. Devuelve codigoJSON -> índice de feature.
 */
export function emparejar(comunas: readonly Comuna[], features: readonly GeoFeature[]): Map<string, number> {
  const porCodigo = new Map<string, number>()
  const porNombre = new Map<string, number>()
  features.forEach((f, i) => {
    porCodigo.set(f.properties.codigo, i)
    porNombre.set(slug(f.properties.nombre), i)
  })
  const usados = new Set<number>()
  const out = new Map<string, number>()
  for (const c of comunas) {
    let i = porCodigo.get(c.codigo)
    if (i === undefined) i = porNombre.get(slug(c.nombre))
    if (i === undefined) i = porNombre.get(slug(c.codigo))
    if (i !== undefined && !usados.has(i)) {
      out.set(c.codigo, i)
      usados.add(i)
    }
  }
  return out
}

/** Círculo aproximado como polígono, para cuando no hay GeoJSON de comunas. */
export function circulo(lon: number, lat: number, radioKm: number, lados = 28): [number, number][] {
  const dLat = radioKm / 110.57
  const dLon = radioKm / (111.32 * Math.cos((lat * Math.PI) / 180))
  const pts: [number, number][] = []
  for (let i = 0; i <= lados; i++) {
    const a = (i / lados) * 2 * Math.PI
    pts.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)])
  }
  return pts
}

export function featuresDeRespaldo(comunas: readonly Comuna[]): GeoFeature[] {
  return comunas.map((c) => ({
    type: 'Feature',
    properties: { codigo: c.codigo, nombre: c.nombre, simCodigo: c.codigo },
    geometry: { type: 'Polygon', coordinates: [circulo(c.lon, c.lat, 3.2)] },
  }))
}

/** Marca cada feature con el código del JSON con el que se emparejó (o undefined: sin dato). */
export function anotar(features: readonly GeoFeature[], pares: ReadonlyMap<string, number>): GeoFeature[] {
  const inverso = new Map<number, string>()
  for (const [cod, i] of pares) inverso.set(i, cod)
  return features.map((f, i) => ({ ...f, properties: { ...f.properties, simCodigo: inverso.get(i) } }))
}
