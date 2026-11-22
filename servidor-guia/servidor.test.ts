import assert from 'node:assert/strict'
import type { AddressInfo } from 'node:net'
import { test } from 'node:test'
import type { ClienteClaude } from './claude.ts'
import { crearServidor, crearTopeDiario, ipCliente } from './servidor.ts'
import type { IncomingMessage } from 'node:http'

const ORIGEN = 'http://localhost:5173'

function cliente(texto: string): ClienteClaude {
  return { beta: { messages: { create: async () => ({ stop_reason: 'end_turn', content: [{ type: 'text', text: texto }] }) } } }
}

async function conServidor(c: ClienteClaude | null, f: (base: string) => Promise<void>) {
  const s = crearServidor(() => c, [ORIGEN])
  await new Promise<void>((ok) => s.listen(0, '127.0.0.1', ok))
  try {
    await f(`http://127.0.0.1:${(s.address() as AddressInfo).port}`)
  } finally {
    await new Promise((ok) => s.close(ok))
  }
}

const cuerpo = JSON.stringify({ caso: 'mi hijo tiene asma', perfil: 'Comprar una vivienda', prioridades: { pm25_anual: 8 } })

test('POST /interpretar returns the validated interpretation with CORS for the allowed origin', async () => {
  const c = cliente(JSON.stringify({ ajustes: [{ variable: 'pm25_anual', grado: 10, cita: 'mi hijo tiene asma' }], indicadores: [], no_medido: [] }))
  await conServidor(c, async (base) => {
    const r = await fetch(`${base}/interpretar`, { method: 'POST', headers: { origin: ORIGEN, 'content-type': 'application/json' }, body: cuerpo })
    assert.equal(r.status, 200)
    assert.equal(r.headers.get('access-control-allow-origin'), ORIGEN)
    assert.deepEqual((await r.json()).ajustes, [{ variable: 'pm25_anual', grado: 10, cita: 'mi hijo tiene asma' }])
  })
})

test('other origins get no CORS header', async () => {
  await conServidor(cliente('{}'), async (base) => {
    const r = await fetch(`${base}/interpretar`, { method: 'OPTIONS', headers: { origin: 'https://otro.example' } })
    assert.equal(r.headers.get('access-control-allow-origin'), null)
  })
})

test('a malformed request is a 400 and never reaches Claude', async () => {
  let llamadas = 0
  const c: ClienteClaude = { beta: { messages: { create: async () => (llamadas++, { stop_reason: 'end_turn', content: [] }) } } }
  await conServidor(c, async (base) => {
    const r = await fetch(`${base}/interpretar`, { method: 'POST', headers: { origin: ORIGEN }, body: '{"caso": ""}' })
    assert.equal(r.status, 400)
  })
  assert.equal(llamadas, 0)
})

test('without an API key the server answers 503 instead of failing', async () => {
  await conServidor(null, async (base) => {
    const r = await fetch(`${base}/interpretar`, { method: 'POST', headers: { origin: ORIGEN }, body: cuerpo })
    assert.equal(r.status, 503)
    assert.equal((await fetch(`${base}/salud`)).status, 200)
  })
})

test('unknown routes are 404', async () => {
  await conServidor(cliente('{}'), async (base) => {
    assert.equal((await fetch(`${base}/otra`, { method: 'POST' })).status, 404)
  })
})

test('an oversized body gets a 413 instead of hanging', async () => {
  await conServidor(cliente('{}'), async (base) => {
    const r = await fetch(`${base}/interpretar`, { method: 'POST', headers: { origin: ORIGEN }, body: 'x'.repeat(20_000) })
    assert.equal(r.status, 413)
  })
})

test('POST /guia rejects a body that is not a guide request', async () => {
  await conServidor(cliente('texto'), async (base) => {
    const r = await fetch(`${base}/guia`, { method: 'POST', headers: { origin: ORIGEN }, body: JSON.stringify({ cualquier: 'cosa' }) })
    assert.equal(r.status, 400)
  })
})

test('each client gets a limited number of model calls per minute', async () => {
  const c = cliente(JSON.stringify({ ajustes: [], indicadores: [], no_medido: [] }))
  const s = crearServidor(() => c, [ORIGEN], { pedidosPorMinuto: 2 })
  await new Promise<void>((ok) => s.listen(0, '127.0.0.1', ok))
  const base = `http://127.0.0.1:${(s.address() as AddressInfo).port}`
  try {
    const estados = []
    // Different cases: identical ones would be answered from the cache, which does not count.
    for (let i = 0; i < 3; i++) {
      const body = JSON.stringify({ caso: `mi hijo tiene asma ${i}`, perfil: 'Comprar una vivienda', prioridades: { pm25_anual: 8 } })
      estados.push((await fetch(`${base}/interpretar`, { method: 'POST', body })).status)
    }
    assert.deepEqual(estados, [200, 200, 429])
  } finally {
    await new Promise((ok) => s.close(ok))
  }
})

/** Fake client that counts calls and can be held open until released. */
function contador(texto: string) {
  let llamadas = 0
  let soltar: () => void = () => {}
  const listo = new Promise<void>((ok) => (soltar = ok))
  const c: ClienteClaude = {
    beta: { messages: { create: async () => (llamadas++, await listo, { stop_reason: 'end_turn', content: [{ type: 'text', text: texto }] }) } },
  }
  return { c, llamadas: () => llamadas, soltar: () => soltar() }
}

const LECTURA = JSON.stringify({ ajustes: [], indicadores: [], no_medido: [], preguntas: ['¿Es para vivir o para una empresa?'] })
const post = (base: string, body: string) => fetch(`${base}/interpretar`, { method: 'POST', headers: { 'content-type': 'application/json' }, body })

test('an identical request is answered from the cache: one model call, and it does not use up the limit', async () => {
  const k = contador(LECTURA)
  k.soltar()
  const s = crearServidor(() => k.c, [ORIGEN], { pedidosPorMinuto: 1 })
  await new Promise<void>((ok) => s.listen(0, '127.0.0.1', ok))
  const base = `http://127.0.0.1:${(s.address() as AddressInfo).port}`
  try {
    const a = await post(base, cuerpo)
    const b = await post(base, cuerpo)
    assert.equal(a.status, 200)
    assert.equal(b.status, 200)
    assert.deepEqual(await b.json(), await a.json())
    assert.equal(k.llamadas(), 1)
    // The limit (1 per minute) was spent by the first call; a different case is now refused.
    assert.equal((await post(base, cuerpo.replace('asma', 'bronquitis'))).status, 429)
  } finally {
    await new Promise((ok) => s.close(ok))
  }
})

test('identical requests in flight share one model call', async () => {
  const k = contador(LECTURA)
  await conServidor(k.c, async (base) => {
    const dos = Promise.all([post(base, cuerpo), post(base, cuerpo)])
    await new Promise((ok) => setTimeout(ok, 50))
    k.soltar()
    const [a, b] = await dos
    assert.deepEqual([a.status, b.status], [200, 200])
    assert.equal(k.llamadas(), 1)
  })
})

test('failed answers are not cached', async () => {
  let llamadas = 0
  const c: ClienteClaude = { beta: { messages: { create: async () => (llamadas++, { stop_reason: 'refusal', content: [] }) } } }
  await conServidor(c, async (base) => {
    assert.equal((await post(base, cuerpo)).status, 502)
    assert.equal((await post(base, cuerpo)).status, 502)
    assert.equal(llamadas, 2)
  })
})

test('ipCliente trusts X-Forwarded-For only as far as the configured proxy hops', () => {
  const req = (xff?: string) => ({ socket: { remoteAddress: '10.0.0.1' }, headers: xff ? { 'x-forwarded-for': xff } : {} }) as unknown as IncomingMessage
  assert.equal(ipCliente(req('6.6.6.6, 200.1.1.1'), 0), '10.0.0.1')
  // One trusted hop: the last entry is what the proxy saw; the forged first one is ignored.
  assert.equal(ipCliente(req('6.6.6.6, 200.1.1.1'), 1), '200.1.1.1')
  assert.equal(ipCliente(req('200.1.1.1'), 1), '200.1.1.1')
  assert.equal(ipCliente(req(), 1), '10.0.0.1')
})

test('the daily cap refuses model calls past the limit until the next UTC day; 0 means no cap', () => {
  let t = Date.UTC(2026, 10, 21, 23, 0)
  const queda = crearTopeDiario(2, () => t)
  assert.deepEqual([queda(), queda(), queda()], [true, true, false])
  t = Date.UTC(2026, 10, 22, 0, 1)
  assert.equal(queda(), true)
  const sinTope = crearTopeDiario(0)
  assert.ok(Array.from({ length: 50 }, sinTope).every(Boolean))
})

test('past the daily cap the server answers 429 without calling Claude, but cached answers still go out', async () => {
  let llamadas = 0
  const c: ClienteClaude = { beta: { messages: { create: async () => (llamadas++, { stop_reason: 'end_turn', content: [{ type: 'text', text: LECTURA }] }) } } }
  const s = crearServidor(() => c, [ORIGEN], { topeDiario: 1 })
  await new Promise<void>((ok) => s.listen(0, '127.0.0.1', ok))
  const base = `http://127.0.0.1:${(s.address() as AddressInfo).port}`
  try {
    assert.equal((await post(base, cuerpo)).status, 200)
    const otro = await post(base, cuerpo.replace('asma', 'bronquitis'))
    assert.equal(otro.status, 429)
    assert.match((await otro.json()).error, /cupo/)
    assert.equal((await post(base, cuerpo)).status, 200)
    assert.equal(llamadas, 1)
  } finally {
    await new Promise((ok) => s.close(ok))
  }
})

test('GET /salud shows how the rate limit sees the caller, to set PROXIES_CONFIABLES from evidence', async () => {
  const s = crearServidor(() => null, [ORIGEN], { proxies: 1 })
  await new Promise<void>((ok) => s.listen(0, '127.0.0.1', ok))
  const base = `http://127.0.0.1:${(s.address() as AddressInfo).port}`
  try {
    const r = await (await fetch(`${base}/salud`, { headers: { 'x-forwarded-for': '6.6.6.6, 200.1.1.1' } })).json()
    assert.deepEqual(r, { ok: true, clave: false, ip: '200.1.1.1', proxies: 1, cadena: ['6.6.6.6', '200.1.1.1'], directa: '127.0.0.1' })
  } finally {
    await new Promise((ok) => s.close(ok))
  }
})
