const nf = new Map<number, Intl.NumberFormat>()

function formatter(digits: number): Intl.NumberFormat {
  let f = nf.get(digits)
  if (!f) {
    f = new Intl.NumberFormat('es-CL', { minimumFractionDigits: digits, maximumFractionDigits: digits })
    nf.set(digits, f)
  }
  return f
}

/** Número con coma decimal y signo menos tipográfico. */
export function fmt(n: number, digits = 1): string {
  if (!Number.isFinite(n)) return 'sin dato'
  return formatter(digits).format(n).replace('-', '−')
}

export function fmtSigned(n: number, digits = 1): string {
  if (!Number.isFinite(n)) return 'sin dato'
  return (n > 0 ? '+' : '') + fmt(n, digits)
}

/** "41,4 (38,9–45,2) µg/m³": una proyección nunca se muestra sin su banda. */
export function fmtBanda(p50: number, p10: number, p90: number, unidad = '', digits = 1): string {
  const u = unidad ? ` ${unidad}` : ''
  return `${fmt(p50, digits)} (${fmt(p10, digits)}–${fmt(p90, digits)})${u}`
}

export function fmtPct(n: number): string {
  return `${fmt(n * 100, 0)} %`
}

/** Solo http y https. Cualquier otra cosa (javascript:, data:, relativa) se descarta. */
export function safeUrl(raw: unknown): string | null {
  if (typeof raw !== 'string') return null
  try {
    const u = new URL(raw.trim())
    return u.protocol === 'http:' || u.protocol === 'https:' ? u.href : null
  } catch {
    return null
  }
}

/** Minúsculas, sin tildes ni signos: para comparar nombres de comuna. */
export function slug(s: string): string {
  return s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

