import { validarSimulacion, type Resultado } from './validate'

async function leerJson(url: string): Promise<unknown> {
  const r = await fetch(url, { cache: 'no-cache' })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json() // si el servidor devuelve index.html, esto lanza y se usa el respaldo
}

/** Pide datos/simulacion.json; si falta, cae al ejemplo (datos/ejemplo.json). */
export async function cargarSimulacion(): Promise<Resultado> {
  let primario: unknown
  try {
    primario = await leerJson('datos/simulacion.json')
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
export async function cargarDemografia(): Promise<unknown> {
  try {
    return await leerJson('datos/demografia.json')
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

/** Polígonos de las comunas; null si no existen todavía. */
export async function cargarGeo(): Promise<unknown> {
  try {
    return await leerJson('geo/comunas_rm.geojson')
  } catch {
    return null
  }
}
