/** Datos reales de leña (viz/public/datos/lena.json, generado por datos/viz/build_lena.py). Se tratan como no confiables. */

export type Zona = 'A' | 'B'

export interface ComunaLena {
  codigo: string
  nombre: string
  zona: Zona
  /** t/año de MP2,5 por leña; null = sin dato (nunca cero inventado) */
  toneladas: number | null
  poblacion: number
}

export interface ResumenZona {
  comunas: number
  toneladas: number
  parteEmisiones: number
  poblacion: number
  partePoblacion: number
  sinDato: string[]
}

export interface Lena {
  anio: number
  fuente: string
  zonasFuente: string
  comunas: ComunaLena[]
  zonas: Record<Zona, ResumenZona>
  /** comunas cuya zona difiere entre lena.json y la simulación (se usa la de la simulación) */
  discrepancias: string[]
}

type Obj = Record<string, unknown>
const esObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)
const esNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

/** Totales y partes por zona, recalculados desde las filas por comuna (no se confía en los totales del archivo). */
export function agregarZonas(comunas: readonly ComunaLena[]): Record<Zona, ResumenZona> {
  const vacio = (): ResumenZona => ({ comunas: 0, toneladas: 0, parteEmisiones: 0, poblacion: 0, partePoblacion: 0, sinDato: [] })
  const z: Record<Zona, ResumenZona> = { A: vacio(), B: vacio() }
  for (const c of comunas) {
    const r = z[c.zona]
    r.comunas++
    r.poblacion += c.poblacion
    if (c.toneladas === null) r.sinDato.push(c.nombre)
    else r.toneladas += c.toneladas
  }
  const t = z.A.toneladas + z.B.toneladas
  const p = z.A.poblacion + z.B.poblacion
  for (const k of ['A', 'B'] as const) {
    z[k].parteEmisiones = t > 0 ? z[k].toneladas / t : 0
    z[k].partePoblacion = p > 0 ? z[k].poblacion / p : 0
  }
  return z
}

/**
 * Lee y valida lena.json. Si se entrega la zona de cada comuna según la simulación (`zona_ppda`),
 * esa manda y las diferencias quedan anotadas. Devuelve null si el archivo no sirve.
 */
export function leerLena(raw: unknown, zonasSimulacion?: ReadonlyMap<string, Zona>): Lena | null {
  if (!esObj(raw) || !Array.isArray(raw.comunas)) return null
  const meta = esObj(raw.meta) ? raw.meta : {}
  const comunas: ComunaLena[] = []
  const discrepancias: string[] = []
  for (const c of raw.comunas) {
    if (!esObj(c) || typeof c.codigo !== 'string' || typeof c.nombre !== 'string') continue
    if (c.zona !== 'A' && c.zona !== 'B') continue
    const t = c.toneladas === null ? null : esNum(c.toneladas) && c.toneladas >= 0 ? c.toneladas : undefined
    if (t === undefined) continue
    const sim = zonasSimulacion?.get(c.codigo)
    if (sim && sim !== c.zona) discrepancias.push(c.nombre)
    comunas.push({
      codigo: c.codigo,
      nombre: c.nombre,
      zona: sim ?? c.zona,
      toneladas: t,
      poblacion: esNum(c.poblacion) && c.poblacion >= 0 ? c.poblacion : 0,
    })
  }
  if (comunas.length === 0) return null
  return {
    anio: esNum(meta.anio) ? meta.anio : 0,
    fuente: typeof meta.fuente === 'string' ? meta.fuente : '',
    zonasFuente: typeof meta.zonas === 'string' ? meta.zonas : '',
    comunas,
    zonas: agregarZonas(comunas),
    discrepancias,
  }
}

/** Radio de un disco cuya área es proporcional a las toneladas; el máximo mide `radioMax`. */
export function radioDisco(t: number, tMax: number, radioMax: number): number {
  if (!(t > 0) || !(tMax > 0)) return 0
  return radioMax * Math.sqrt(Math.min(t, tMax) / tMax)
}
