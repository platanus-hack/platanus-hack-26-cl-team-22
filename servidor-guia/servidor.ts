/**
 * HTTP intermediary between the simulator page and the Claude API. The API key lives only here
 * (ANTHROPIC_API_KEY in this process's environment), never in the page or in a VITE_ variable.
 *
 *   POST /interpretar  { caso, perfil, prioridades }  -> { ajustes, indicadores, no_medido }
 *   POST /guia         PedidoGuia (viz/src/lib/guia.ts) -> { texto }
 *   GET  /salud        -> { ok, clave }
 *
 * Run:  ANTHROPIC_API_KEY=... node servidor.ts     (PORT, default 8787; ORIGENES, comma separated)
 */
import Anthropic from '@anthropic-ai/sdk'
import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http'
import { interpretarCaso, redactarGuia, validarPedidoCaso, validarPedidoGuia, type ClienteClaude } from './claude.ts'

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
  opciones: { pedidosPorMinuto?: number } = {},
): Server {
  const permitir = crearLimitador(opciones.pedidosPorMinuto ?? 20)
  return createServer(async (req, res) => {
    const origen = req.headers.origin
    if (origen && origenes.includes(origen)) {
      res.setHeader('access-control-allow-origin', origen)
      res.setHeader('access-control-allow-methods', 'POST, OPTIONS')
      res.setHeader('access-control-allow-headers', 'content-type')
      res.setHeader('vary', 'origin')
    }
    if (req.method === 'OPTIONS') return void res.writeHead(204).end()
    if (req.method === 'GET' && req.url === '/salud') return responder(res, 200, { ok: true, clave: obtenerCliente() !== null })
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
    if (!permitir(req.socket.remoteAddress ?? 'desconocido')) return responder(res, 429, { error: 'demasiados pedidos; espera un minuto' })
    // If the page gives up (it waits 12-15 s), stop the model call instead of spending tokens on it.
    const corte = new AbortController()
    res.on('close', () => {
      if (!res.writableEnded) corte.abort()
    })
    try {
      if (pedidoCaso) {
        const r = await interpretarCaso(cliente, pedidoCaso, corte.signal)
        return r ? responder(res, 200, r) : responder(res, 502, { error: 'sin interpretación' })
      }
      const g = await redactarGuia(cliente, pedidoGuia!, corte.signal)
      return g ? responder(res, 200, g) : responder(res, 502, { error: 'sin guía' })
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
  crearServidor(() => cliente, origenes).listen(puerto, () => {
    console.log(`servidor-guia en http://localhost:${puerto} (clave: ${cliente ? 'sí' : 'no'}; orígenes: ${origenes.join(', ')})`)
  })
}
