import { validarSimulacion, type Resultado } from './validate'

async function leerJson(url: string): Promise<unknown> {
  const r = await fetch(url, { cache: 'no-cache' })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json() // si el servidor devuelve index.html, esto lanza y se usa el respaldo
}

/** Horizonte de la simulación: 10 años (2026–2036, el validado) o 15 (hasta 2040, con los últimos extrapolados). */
export type Horizonte = '10' | '15'
const ARCHIVO_SIM: Record<Horizonte, string> = { '10': 'datos/simulacion.json', '15': 'datos/simulacion-15.json' }

/** Pide la simulación del horizonte pedido; si falta, cae al ejemplo (datos/ejemplo.json). */
export async function cargarSimulacion(horizonte: Horizonte = '10'): Promise<Resultado> {
  let primario: unknown
  try {
    primario = await leerJson(ARCHIVO_SIM[horizonte])
  } catch {
    primario = undefined
  }
  if (primario !== undefined) return validarSimulacion(primario)
  try {
    return validarSimulacion(await leerJson('datos/ejemplo.json'))
  } catch {
    return { ok: false, errores: ['No se encontró datos/simulacion.json ni el archivo de ejemplo.'] }
  }
}

/** Emisiones reales de leña por comuna (datos/lena.json); null si el archivo no está. */
export async function cargarLena(): Promise<unknown> {
  try {
    return await leerJson('datos/lena.json')
  } catch {
    return null
  }
}

/** Parámetros del laboratorio de mudanzas (datos/demografia.json); null si el archivo no está. */
export async function cargarDemografia(horizonte: Horizonte = '10'): Promise<unknown> {
  try {
    return await leerJson(horizonte === '15' ? 'datos/demografia-15.json' : 'datos/demografia.json')
  } catch {
    return null
  }
}

/** Caudales reales por estación (datos/caudales.json) y trazado de los ríos (geo/rios_rm.geojson); null si faltan. */
export async function cargarAgua(): Promise<{ caudales: unknown; rios: unknown }> {
  const leer = (url: string) => leerJson(url).catch(() => null)
  const [caudales, rios] = await Promise.all([leer('datos/caudales.json'), leer('geo/rios_rm.geojson')])
  return { caudales, rios }
}

/** Indicadores reales para quien quiere invertir (datos/inversion.json); null si el archivo no está. */
export async function cargarInversion(): Promise<unknown> {
  try {
    return await leerJson('datos/inversion.json')
  } catch {
    return null
  }
}

/** Polígonos de las comunas; null si no existen todavía. */
export async function cargarGeo(): Promise<unknown> {
  try {
    return await leerJson('geo/comunas_rm.geojson')
  } catch {
    return null
  }
}
