export type RGB = [number, number, number]

const PASOS = 7

/** Respaldo idéntico a tokens.css, por si la hoja de estilos no cargó. */
const RAMPA_RESPALDO = ['#F1E7D0', '#E8CFA0', '#DDB075', '#CC8A55', '#B5623F', '#8F3E2D', '#5E2220']

export function hexARgb(hex: string): RGB {
  const h = hex.trim().replace('#', '')
  const n = parseInt(h.length === 3 ? h.replace(/(.)/g, '$1$1') : h, 16)
  if (!Number.isFinite(n)) return [128, 128, 128]
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

export function leerToken(nombre: string, respaldo: string): string {
  if (typeof document === 'undefined') return respaldo
  const v = getComputedStyle(document.documentElement).getPropertyValue(nombre).trim()
  return v || respaldo
}

/** Rampa secuencial definida en tokens.css (--rampa-1 a --rampa-7). */
export function leerRampa(): string[] {
  return Array.from({ length: PASOS }, (_, i) => leerToken(`--rampa-${i + 1}`, RAMPA_RESPALDO[i]!))
}

/** Respaldo de la paleta divergente (--div-1 a --div-5): mejora fuerte, mejora leve, neutro, empeora leve, empeora fuerte. */
const DIV_RESPALDO = ['#2F6F6E', '#9DC2BA', '#EBE5D6', '#DFAE98', '#9B3F35']

/** Paleta divergente definida en tokens.css (--div-1 a --div-5). Índice 0 es la mayor mejora. */
export function leerDivergente(): string[] {
  return DIV_RESPALDO.map((r, i) => leerToken(`--div-${i + 1}`, r))
}

/** Clase 0..6 de un valor dentro del dominio. Si menor es mejor, el marrón oscuro es lo peor. */
export function clase(valor: number, dominio: [number, number], mejor: 'menor' | 'mayor'): number {
  const [lo, hi] = dominio
  const t = hi === lo ? 0.5 : Math.min(1, Math.max(0, (valor - lo) / (hi - lo)))
  const c = Math.min(PASOS - 1, Math.floor(t * PASOS))
  return mejor === 'menor' ? c : PASOS - 1 - c
}

/** Bordes de las 7 clases en unidades de la variable. */
export function bordes(dominio: [number, number]): number[] {
  const [lo, hi] = dominio
  return Array.from({ length: PASOS + 1 }, (_, i) => lo + ((hi - lo) * i) / PASOS)
}
