/**
 * HTTP intermediary between the simulator page and the Claude API. The API key lives only here
 * (ANTHROPIC_API_KEY in this process's environment), never in the page or in a VITE_ variable.
 *
 *   POST /interpretar  { caso, perfil, prioridades }  -> { ajustes, indicadores, no_medido, preguntas }
 *   POST /guia         PedidoGuia (viz/src/lib/guia.ts) -> { texto }
 *   GET  /salud        -> { ok, clave, ip, proxies, cadena, directa }  (cadena: X-Forwarded-For as received)
 *
 * Run:  ANTHROPIC_API_KEY=... node servidor.ts     (PORT, default 8787; ORIGENES, comma separated)
 */
import Anthropic from '@anthropic-ai/sdk'
import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http'
import { interpretarCaso, redactarGuia, validarPedidoCaso, validarPedidoGuia, type ClienteClaude } from './claude.ts'
import { crearMemo } from './memo.ts'

const LIMITE_CUERPO = 8_000
const ORIGENES_DEFECTO = ['http://localhost:5173', 'http://localhost:4173']

const DEMASIADO_GRANDE = Symbol('demasiado grande')

/** Parsed JSON body, null if it is not JSON, or DEMASIADO_GRANDE past the byte limit (always resolves). */
function leerCuerpo(req: IncomingMessage): Promise<unknown> {
  return new Promise((ok) => {
    const partes: Buffer[] = []
    let bytes = 0
    let listo = false
    const terminar = (v: unknown) => {
      if (!listo) {
        listo = true
        ok(v)
      }
    }
    req.on('data', (c: Buffer) => {
      bytes += c.length
      if (bytes > LIMITE_CUERPO) {
        terminar(DEMASIADO_GRANDE)
        req.pause()
        return
      }
      partes.push(c)
    })
    req.on('end', () => {
      try {
        terminar(JSON.parse(Buffer.concat(partes).toString('utf8')))
      } catch {
        terminar(null)
      }
    })
    req.on('error', () => terminar(null))
    req.on('close', () => terminar(null))
  })
}

/** Fixed one-minute window per client address: enough to stop a script from draining the API key. */
function crearLimitador(porMinuto: number) {
  const ventanas = new Map<string, { desde: number; n: number }>()
  return (quien: string): boolean => {
    const ahora = Date.now()
    const v = ventanas.get(quien)
    if (!v || ahora - v.desde >= 60_000) {
      ventanas.set(quien, { desde: ahora, n: 1 })
      if (ventanas.size > 10_000) ventanas.clear()
      return true
    }
    v.n++
    return v.n <= porMinuto
  }
}

/**
 * Who is asking, for the rate limit. Behind a proxy (Render) every request comes from the proxy's
 * address, so all visitors would share one limit; with `proxies` trusted hops the client is the entry
 * that many places from the end of X-Forwarded-For (earlier entries can be forged by the client).
 */
export function ipCliente(req: IncomingMessage, proxies: number): string {
  const directa = req.socket.remoteAddress ?? 'desconocido'
  if (proxies <= 0) return directa
  const lista = cadenaReenvio(req)
  return lista[lista.length - proxies] ?? directa
}

/** X-Forwarded-For as a list, first entry first (as the client or the first proxy wrote it). */
function cadenaReenvio(req: IncomingMessage): string[] {
  const cabecera = req.headers['x-forwarded-for']
  return (Array.isArray(cabecera) ? cabecera.join(',') : (cabecera ?? '')).split(',').map((s) => s.trim()).filter(Boolean)
}

/**
 * What GET /salud shows so PROXIES_CONFIABLES can be set from evidence: Render's docs do not say how
 * many hops it adds. Only the caller's own request headers are echoed back.
 */
export function diagnosticoIp(req: IncomingMessage, proxies: number) {
  return { ip: ipCliente(req, proxies), proxies, cadena: cadenaReenvio(req), directa: req.socket.remoteAddress ?? null }
}

/**
 * Global cap on model calls per UTC day, across every visitor: the per-address limit alone does not stop
 * someone with many addresses from spending the key. 0 or less means no cap.
 */
export function crearTopeDiario(tope: number, ahora: () => number = Date.now) {
  let dia = -1
  let usadas = 0
  return (): boolean => {
    if (tope <= 0) return true
    const hoy = Math.floor(ahora() / 86_400_000)
    if (hoy !== dia) {
      dia = hoy
      usadas = 0
    }
    if (usadas >= tope) return false
    usadas++
    return true
  }
}

function responder(res: ServerResponse, estado: number, cuerpo: unknown) {
  res.writeHead(estado, { 'content-type': 'application/json; charset=utf-8' })
  res.end(JSON.stringify(cuerpo))
}

function estadoDeError(e: unknown): number {
  if (e instanceof Anthropic.RateLimitError) return 429
  if (e instanceof Anthropic.APIConnectionError) return 502
  if (e instanceof Anthropic.APIError) return 502
  return 500
}

/** `obtenerCliente` returns null when there is no API key; the routes then answer 503. */
export function crearServidor(
  obtenerCliente: () => ClienteClaude | null,
  origenes: readonly string[],
  opciones: { pedidosPorMinuto?: number; proxies?: number; memoTtlMs?: number; topeDiario?: number } = {},
): Server {
  const quedaCupo = crearTopeDiario(opciones.topeDiario ?? 0)
  const permitir = crearLimitador(opciones.pedidosPorMinuto ?? 20)
  const proxies = opciones.proxies ?? 0
  // Answers depend only on the validated request, so identical requests can share one.
  const memo = crearMemo<object>(opciones.memoTtlMs ?? 6 * 60 * 60_000, 500)
  return createServer(async (req, res) => {
    const origen = req.headers.origin
    if (origen && origenes.includes(origen)) {
      res.setHeader('access-control-allow-origin', origen)
      res.setHeader('access-control-allow-methods', 'POST, OPTIONS')
      res.setHeader('access-control-allow-headers', 'content-type')
      res.setHeader('vary', 'origin')
    }
    if (req.method === 'OPTIONS') return void res.writeHead(204).end()
    if (req.method === 'GET' && req.url === '/salud') return responder(res, 200, { ok: true, clave: obtenerCliente() !== null, ...diagnosticoIp(req, proxies) })
    if (req.method !== 'POST' || (req.url !== '/interpretar' && req.url !== '/guia')) return responder(res, 404, { error: 'no existe' })

    const cliente = obtenerCliente()
    if (!cliente) return responder(res, 503, { error: 'falta ANTHROPIC_API_KEY en el servidor' })
    const cuerpo = await leerCuerpo(req)
    if (cuerpo === DEMASIADO_GRANDE) {
      res.setHeader('connection', 'close')
      return responder(res, 413, { error: 'pedido demasiado grande' })
    }
    const pedidoCaso = req.url === '/interpretar' ? validarPedidoCaso(cuerpo) : null
    const pedidoGuia = req.url === '/guia' ? validarPedidoGuia(cuerpo) : null
    if (!pedidoCaso && !pedidoGuia) return responder(res, 400, { error: 'pedido no válido' })
    const clave = `${req.url} ${JSON.stringify(pedidoCaso ?? pedidoGuia)}`
    // A cached answer costs nothing, so it does not count against the limit.
    const guardado = memo.leer(clave)
    if (guardado) return responder(res, 200, guardado)
    if (!permitir(ipCliente(req, proxies))) return responder(res, 429, { error: 'demasiados pedidos; espera un minuto' })
    if (!quedaCupo()) return responder(res, 429, { error: 'se agotó el cupo de consultas de hoy' })
    // If the page gives up (it waits 12-15 s), stop the model call instead of spending tokens on it;
    // an identical request still waiting keeps the shared call alive.
    const corte = new AbortController()
    res.on('close', () => {
      if (!res.writableEnded) corte.abort()
    })
    try {
      const r = await memo.calcular(
        clave,
        (signal) => (pedidoCaso ? interpretarCaso(cliente, pedidoCaso, signal) : redactarGuia(cliente, pedidoGuia!, signal)),
        corte.signal,
      )
      if (corte.signal.aborted) return
      return r ? responder(res, 200, r) : responder(res, 502, { error: pedidoCaso ? 'sin interpretación' : 'sin guía' })
    } catch (e) {
      if (corte.signal.aborted) return
      console.error('Claude API:', e instanceof Anthropic.APIError ? `${e.status} ${e.message}` : e)
      return responder(res, estadoDeError(e), { error: 'falló la llamada al modelo' })
    }
  })
}

if (import.meta.main) {
  const clave = process.env.ANTHROPIC_API_KEY
  // Bounded wait: the page gives up after 12-15 s, so a longer call would only spend tokens.
  const cliente = clave ? (new Anthropic({ timeout: 20_000, maxRetries: 1 }) as unknown as ClienteClaude) : null
  const origenes = process.env.ORIGENES ? process.env.ORIGENES.split(',').map((s) => s.trim()) : ORIGENES_DEFECTO
  const puerto = Number(process.env.PORT ?? 8787)
  // Trusted proxy hops in front of this process. Render's docs do not state it: set it from GET /salud
  // (see README, «Operación»).
  const proxies = Number(process.env.PROXIES_CONFIABLES ?? 0) || 0
  // Model calls per UTC day for the whole service (0 = no cap).
  const topeDiario = Number(process.env.TOPE_DIARIO ?? 0) || 0
  crearServidor(() => cliente, origenes, { proxies, topeDiario }).listen(puerto, () => {
    console.log(`servidor-guia en http://localhost:${puerto} (clave: ${cliente ? 'sí' : 'no'}; orígenes: ${origenes.join(', ')})`)
  })
}
