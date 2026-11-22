/**
 * Guía personalizada escrita por un modelo de lenguaje, pedida a un intermediario propio.
 * La clave del modelo vive en ese intermediario, nunca en esta página. Si no hay intermediario
 * configurado, tarda demasiado o responde algo que no calza, la interfaz usa su explicación propia.
 *
 * Contrato: POST con JSON `PedidoGuia`; respuesta JSON `{ "texto": string }`.
 * El modelo solo redacta con los números que recibe; el orden de las comunas lo calcula siempre el índice.
 */
export interface PedidoGuia {
  perfil: string
  /** el caso que escribió la persona */
  contexto: string
  prioridades: Record<string, number>
  anio: number
  /** las comunas de menor riesgo, con los números que el modelo puede citar */
  top: { comuna: string; riesgo: number; variables: { nombre: string; valor: number | null; unidad: string; riesgo: number }[] }[]
  /** lo que el modelo no mide para este perfil */
  falta?: string
}

export interface Guia {
  texto: string
}

export const LARGO_GUIA = 600
const ESPERA_MS = 12_000

/**
 * Shortens to LARGO_GUIA at the last full sentence; with no sentence end in range, at the last word
 * followed by an ellipsis, so the page never shows a word cut in half.
 */
function acortar(texto: string): string {
  if (texto.length <= LARGO_GUIA) return texto
  const cabe = texto.slice(0, LARGO_GUIA)
  const fin = Math.max(cabe.lastIndexOf('. '), cabe.lastIndexOf('; '))
  if (fin > 0) return cabe.slice(0, fin + 1)
  const espacio = cabe.lastIndexOf(' ', LARGO_GUIA - 1)
  return (espacio > 0 ? cabe.slice(0, espacio) : cabe.slice(0, LARGO_GUIA - 1)) + '…'
}

/** Valida lo que llega de fuera: solo texto, sin saltos y acotado. */
export function limpiarGuia(raw: unknown): Guia | null {
  if (typeof raw !== 'object' || raw === null) return null
  const r = raw as Record<string, unknown>
  if (typeof r.texto !== 'string') return null
  const texto = acortar(r.texto.replace(/\s+/g, ' ').trim())
  if (!texto) return null
  return { texto }
}

/** Dirección del intermediario (variable de entorno VITE_GUIA_URL al construir); solo https o localhost. */
export function urlGuia(raw: string | undefined): string | null {
  if (!raw) return null
  try {
    const u = new URL(raw)
    const local = u.hostname === 'localhost' || u.hostname === '127.0.0.1'
    return u.protocol === 'https:' || (u.protocol === 'http:' && local) ? u.href : null
  } catch {
    return null
  }
}

export async function pedirGuia(url: string, pedido: PedidoGuia, f: typeof fetch = fetch): Promise<Guia | null> {
  const corte = new AbortController()
  const t = setTimeout(() => corte.abort(), ESPERA_MS)
  try {
    const r = await f(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(pedido),
      signal: corte.signal,
      credentials: 'omit',
    })
    if (!r.ok) return null
    return limpiarGuia(await r.json())
  } catch {
    return null
  } finally {
    clearTimeout(t)
  }
}
