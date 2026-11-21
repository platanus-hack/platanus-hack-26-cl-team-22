import { fmt } from './format'
import type { Mejor } from './types'

/**
 * Cortes de los cinco niveles de PM2,5 de invierno, en µg/m³: hasta 20, hasta 30, hasta 40, hasta 50 y más de 50.
 * Referencia provisional: parten de la norma anual de 20 µg/m³ y suben de 10 en 10.
 * Pendiente de confirmación del equipo; si cambian, basta con editar esta lista.
 */
export const CORTES_PM25: readonly number[] = [20, 30, 40, 50]

/** Norma anual chilena de PM2,5 (µg/m³); se usa si el archivo no trae `impacto.norma_ugm3`. */
export const NORMA_ANUAL_PM25 = 20

/**
 * Seis pasos para medias anuales, relativos a la norma anual N: hasta 0,5 N, 0,75 N, N, 1,15 N, 1,3 N y más.
 * Con N = 20: hasta 10, 15, 20, 23, 26 y más de 26 µg/m³. Referencia provisional pendiente del equipo:
 * las medias anuales del modelo se concentran entre 20 y 26, y estos pasos reparten ese tramo.
 */
export const FACTORES_NORMA: readonly number[] = [0.5, 0.75, 1, 1.15, 1.3]

export function cortesAnuales(norma: number = NORMA_ANUAL_PM25): number[] {
  return FACTORES_NORMA.map((f) => Math.round(f * norma * 10 + 1e-6) / 10)
}

/** Número de papeles cálidos de nivel (--nivel-0 a --nivel-5). */
export const PAPELES_NIVEL = 6

export interface TablaNiveles {
  cortes: readonly number[]
  /** valor de la norma si los cortes se definen respecto de ella (para marcarla en la leyenda) */
  norma: number | null
}

/** Tabla que corresponde a una variable: relativa a la norma anual si su id o nombre dice "anual"; si no, la de invierno. */
export function tablaPara(v: { id: string; nombre: string }, norma?: number): TablaNiveles {
  if (/anual/i.test(v.id) || /anual/i.test(v.nombre)) {
    const n = norma !== undefined && norma > 0 ? norma : NORMA_ANUAL_PM25
    return { cortes: cortesAnuales(n), norma: n }
  }
  return { cortes: CORTES_PM25, norma: null }
}

/** Cortes de una variable (atajo de tablaPara). */
export function cortesPara(v: { id: string; nombre: string }, norma?: number): readonly number[] {
  return tablaPara(v, norma).cortes
}

/**
 * Papel (0..5) de un nivel. Con seis niveles es directo; con cinco (invierno) se salta el paso
 * intercalado entre naranjo y rojo, para conservar la paleta original de cinco.
 */
export function papelNivel(i: number, cortes: readonly number[]): number {
  const n = cortes.length + 1
  if (n === PAPELES_NIVEL) return Math.max(0, Math.min(5, i))
  if (n === 5) return [0, 1, 2, 4, 5][Math.max(0, Math.min(4, i))]!
  return Math.round((Math.max(0, Math.min(n - 1, i)) * (PAPELES_NIVEL - 1)) / Math.max(1, n - 1))
}

/** Nivel de un valor. Un valor igual a un corte queda en el nivel de abajo. */
export function nivel(v: number, cortes: readonly number[] = CORTES_PM25): number {
  let i = 0
  while (i < cortes.length && v > cortes[i]!) i++
  return i
}

const num = (n: number) => fmt(n, Number.isInteger(n) ? 0 : 1)

/** Texto corto del rango de un nivel: "hasta 20", "20 a 30", "más de 50". */
export function textoNivel(i: number, cortes: readonly number[] = CORTES_PM25): string {
  if (i <= 0) return `hasta ${num(cortes[0]!)}`
  if (i >= cortes.length) return `más de ${num(cortes[cortes.length - 1]!)}`
  return `${num(cortes[i - 1]!)} a ${num(cortes[i]!)}`
}

export interface Cruce {
  /** nivel vecino que alcanza la banda */
  nivel: number
  /** tamaño del recorte interior respecto de la comuna (0 a 1, lineal) */
  escala: number
}

interface Banda3 {
  p10: number
  p50: number
  p90: number
}

/** Tamaño del recorte interior: crece con el ancho relativo de la banda. */
export function escalaRecorte(p: Banda3): number {
  const ancho = Math.max(0, p.p90 - p.p10) / Math.max(1, Math.abs(p.p50))
  // Tope 0,55 (un 30 % del área): el papel propio de la comuna siempre domina sobre el del nivel vecino.
  return Math.min(0.55, Math.max(0.25, 0.25 + 2 * ancho))
}

/**
 * Si la banda p10 a p90 cruza un corte de nivel, devuelve el nivel vecino que alcanza
 * (el lado con más banda más allá del corte) y el tamaño del recorte; si no, null.
 */
export function cruceBanda(p: Banda3, cortes: readonly number[] = CORTES_PM25): Cruce | null {
  const n = nivel(p.p50, cortes)
  const abajoCorte = n > 0 ? cortes[n - 1] : undefined
  const arribaCorte = n < cortes.length ? cortes[n] : undefined
  const arriba = arribaCorte !== undefined && p.p90 > arribaCorte ? p.p90 - arribaCorte : 0
  const abajo = abajoCorte !== undefined && p.p10 <= abajoCorte ? abajoCorte - p.p10 + 1e-9 : 0
  if (arriba === 0 && abajo === 0) return null
  return { nivel: arriba >= abajo ? n + 1 : n - 1, escala: escalaRecorte(p) }
}

/** Bajo este cambio de mediana (µg/m³) una comuna cuenta como "sin cambio". Pequeño porque las medias anuales se mueven poco. */
export const DIF_SIN_CAMBIO = 0.2

/**
 * Paso de una diferencia: 0 sin cambio, −1..−3 mejora y +1..+3 empeora, en tercios de la escala.
 * El signo sigue a `mejor`: si menor es mejor, una baja es mejora.
 */
export function pasoDiferencia(delta: number, max: number, mejor: Mejor, umbral = DIF_SIN_CAMBIO): number {
  if (!Number.isFinite(delta) || Math.abs(delta) < umbral) return 0
  const peor = mejor === 'menor' ? delta : -delta
  const frac = Math.abs(delta) / Math.max(max, umbral)
  const paso = frac <= 1 / 3 ? 1 : frac <= 2 / 3 ? 2 : 3
  return peor > 0 ? paso : -paso
}

/** Bordes de los pasos de diferencia en unidades de la variable: umbral, max/3, 2max/3, max. */
export function bordesPasos(max: number, umbral = DIF_SIN_CAMBIO): number[] {
  return [umbral, max / 3, (2 * max) / 3, max]
}
