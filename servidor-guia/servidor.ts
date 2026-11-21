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
import { interpretarCaso, redactarGuia, validarPedidoCaso, type ClienteClaude } from './claude.ts'

const LIMITE_CUERPO = 8_000
const ORIGENES_DEFECTO = ['http://localhost:5173', 'http://localhost:4173']

function leerCuerpo(req: IncomingMessage): Promise<unknown> {
  return new Promise((ok) => {
    let datos = ''
    req.on('data', (c: Buffer) => {
      datos += c
      if (datos.length > LIMITE_CUERPO) {
        datos = ''
        req.destroy()
      }
    })
    req.on('end', () => {
      try {
        ok(JSON.parse(datos))
      } catch {
        ok(null)
      }
    })
    req.on('error', () => ok(null))
  })
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
export function crearServidor(obtenerCliente: () => ClienteClaude | null, origenes: readonly string[]): Server {
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
    try {
      if (req.url === '/interpretar') {
        const pedido = validarPedidoCaso(cuerpo)
        if (!pedido) return responder(res, 400, { error: 'pedido no válido' })
        const r = await interpretarCaso(cliente, pedido)
        return r ? responder(res, 200, r) : responder(res, 502, { error: 'sin interpretación' })
      }
      if (typeof cuerpo !== 'object' || cuerpo === null) return responder(res, 400, { error: 'pedido no válido' })
      const g = await redactarGuia(cliente, cuerpo as Parameters<typeof redactarGuia>[1])
      return g ? responder(res, 200, g) : responder(res, 502, { error: 'sin guía' })
    } catch (e) {
      console.error('Claude API:', e instanceof Anthropic.APIError ? `${e.status} ${e.message}` : e)
      return responder(res, estadoDeError(e), { error: 'falló la llamada al modelo' })
    }
  })
}

if (import.meta.main) {
  const clave = process.env.ANTHROPIC_API_KEY
  const cliente = clave ? (new Anthropic() as unknown as ClienteClaude) : null
  const origenes = process.env.ORIGENES ? process.env.ORIGENES.split(',').map((s) => s.trim()) : ORIGENES_DEFECTO
  const puerto = Number(process.env.PORT ?? 8787)
  crearServidor(() => cliente, origenes).listen(puerto, () => {
    console.log(`servidor-guia en http://localhost:${puerto} (clave: ${cliente ? 'sí' : 'no'}; orígenes: ${origenes.join(', ')})`)
  })
}
