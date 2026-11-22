import type { Diferencia } from './diferencia'
import { pasoDiferencia } from './niveles'
import type { Mejor } from './types'

export type VistaId = 'riesgo' | 'plan' | 'lena' | 'prueba' | 'mudanzas'

export interface DefVista {
  id: VistaId
  nombre: string
}

const TODAS: DefVista[] = [
  { id: 'riesgo', nombre: 'Riesgo' },
  { id: 'plan', nombre: 'El plan' },
  { id: 'lena', nombre: 'La leña' },
  { id: 'prueba', nombre: 'La prueba' },
  { id: 'mudanzas', nombre: 'Las mudanzas' },
]

/**
 * Vistas en orden; la tecla es su posición. "La prueba" solo existe si el archivo trae validación y
 * "Las mudanzas" (simulación de mudanzas) solo si existe datos/demografia.json.
 */
export function vistasDisponibles(hayValidacion: boolean, hayDemografia = false): DefVista[] {
  return TODAS.filter((v) => (v.id !== 'prueba' || hayValidacion) && (v.id !== 'mudanzas' || hayDemografia))
}

/** Teclas de las tiras de política, en orden: la tecla que se muestra en cada tira. */
export const TECLAS_POLITICA = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'] as const

export type Accion =
  | { tipo: 'vista'; indice: number }
  | { tipo: 'politica'; indice: number }
  | { tipo: 'anio'; paso: 1 | -1 }
  | { tipo: 'jugar' }
  | { tipo: 'diferencia' }
  | { tipo: 'encuadre' }
  | { tipo: 'reencuadrar' }
  | { tipo: 'soltar' }

/** Traduce una tecla a una acción de la pantalla; null si no hace nada. */
export function accionDeTecla(key: string, nVistas: number, nPoliticas: number): Accion | null {
  if (/^[1-9]$/.test(key)) {
    const i = Number(key) - 1
    return i < nVistas ? { tipo: 'vista', indice: i } : null
  }
  const k = key.toLowerCase()
  const ip = (TECLAS_POLITICA as readonly string[]).indexOf(k)
  if (ip >= 0) return ip < nPoliticas ? { tipo: 'politica', indice: ip } : null
  switch (key) {
    case 'ArrowRight':
      return { tipo: 'anio', paso: 1 }
    case 'ArrowLeft':
      return { tipo: 'anio', paso: -1 }
    case ' ':
      return { tipo: 'jugar' }
    case 'Escape':
      return { tipo: 'soltar' }
  }
  if (k === 'd') return { tipo: 'diferencia' }
  if (k === 'm') return { tipo: 'encuadre' }
  if (k === '0') return { tipo: 'reencuadrar' }
  return null
}

export interface ResumenDif {
  mejoran: number
  empeoran: number
  sinCambio: number
  /** la comuna con el mayor cambio absoluto de mediana */
  mayor: { codigo: string; dif: Diferencia } | null
}

/** Cuántas comunas mejoran, empeoran o no cambian (bajo el umbral) y cuál cambia más. */
export function resumirDiferencias(m: ReadonlyMap<string, Diferencia>, mejor: Mejor, max: number): ResumenDif {
  const r: ResumenDif = { mejoran: 0, empeoran: 0, sinCambio: 0, mayor: null }
  for (const [codigo, dif] of m) {
    const p = pasoDiferencia(dif.delta, max, mejor)
    if (p < 0) r.mejoran++
    else if (p > 0) r.empeoran++
    else r.sinCambio++
    if (!r.mayor || Math.abs(dif.delta) > Math.abs(r.mayor.dif.delta)) r.mayor = { codigo, dif }
  }
  return r
}

/** Pasos que dura cada vista en la demostración automática. */
export const PASOS_POR_VISTA = 5

export interface PasoDemo {
  vista: number
  anio: number
  /** índice de política a alternar en este paso, si corresponde */
  alternar: number | null
}

/**
 * Guion de la demostración automática para el paso `n` (0, 1, 2…): recorre las vistas,
 * avanza un año por paso y, en la vista del plan, despega y vuelve a pegar una política.
 */
export function pasoDemo(n: number, vistas: readonly VistaId[], nAnios: number, politicaDemo: number | null): PasoDemo {
  const nv = Math.max(1, vistas.length)
  const vista = Math.floor(n / PASOS_POR_VISTA) % nv
  const sub = n % PASOS_POR_VISTA
  const enPlan = vistas[vista] === 'plan'
  const alternar = enPlan && politicaDemo !== null && (sub === 1 || sub === 4) ? politicaDemo : null
  return { vista, anio: n % Math.max(1, nAnios), alternar }
}

/**
 * Veredicto del modelo contra la mejor alternativa simple, por error (menor es mejor).
 * Diferencias menores que `tolerancia` cuentan como empate: 0,90 contra 0,91 no es ganar.
 */
export function veredicto(errorModelo: number, errorRival: number, tolerancia = 0.05): 'gana' | 'empata' | 'pierde' {
  if (Math.abs(errorModelo - errorRival) < tolerancia) return 'empata'
  return errorModelo < errorRival ? 'gana' : 'pierde'
}

/**
 * Rótulo discreto del modelo: «Modelo de aire · 500 réplicas». Toma `meta.modelo` hasta el primer
 * signo de dos puntos o paréntesis y nunca muestra rutas de archivo del JSON.
 */
export function etiquetaModelo(modelo: string | undefined, replicas: number | undefined, fmtNum: (n: number) => string): string {
  const partes: string[] = []
  if (modelo) {
    let m = modelo.split(/[:(]/)[0]!.trim()
    // la versión interna («v0») no le dice nada a quien mira y suena a borrador
    m = m.replace(/\bv\d+(\.\d+)*\b/gi, '').replace(/\S*[\/]\S*/g, '').replace(/\S+\.(md|json|py|csv)\b/gi, '').replace(/\s+/g, ' ').trim()
    if (m) partes.push(/^modelo\b/i.test(m) ? m.charAt(0).toUpperCase() + m.slice(1) : `Modelo de ${m.charAt(0).toLowerCase()}${m.slice(1)}`)
  }
  if (replicas && replicas > 0) partes.push(`${fmtNum(replicas)} réplicas`)
  return partes.join(' · ')
}

/** Banda de una cantidad: el rango, o «sin variación entre réplicas» si p10 y p90 coinciden. */
export function textoBanda(p10: number, p90: number, fmtNum: (n: number) => string, unidad: string): string {
  if (fmtNum(p10) === fmtNum(p90)) return 'sin variación entre réplicas'
  return `${fmtNum(p10)}–${fmtNum(p90)}${unidad ? ` ${unidad}` : ''}`
}
