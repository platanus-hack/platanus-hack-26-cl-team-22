import assert from 'node:assert/strict'
import type { AddressInfo } from 'node:net'
import { test } from 'node:test'
import type { ClienteClaude } from './claude.ts'
import { crearServidor } from './servidor.ts'

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
    for (let i = 0; i < 3; i++) estados.push((await fetch(`${base}/interpretar`, { method: 'POST', body: cuerpo })).status)
    assert.deepEqual(estados, [200, 200, 429])
  } finally {
    await new Promise((ok) => s.close(ok))
  }
})

test('POST /preguntar returns at most two questions and rejects a bad body without calling Claude', async () => {
  await conServidor(cliente(JSON.stringify({ preguntas: ['¿Es para vivir o para una empresa?', '¿Hay niños o personas con asma?', '¿Una tercera pregunta?'] })), async (base) => {
    const r = await fetch(`${base}/preguntar`, { method: 'POST', headers: { origin: ORIGEN, 'content-type': 'application/json' }, body: JSON.stringify({ caso: 'quiero evaluar el aire' }) })
    assert.equal(r.status, 200)
    assert.equal((await r.json()).preguntas.length, 2)
    const mala = await fetch(`${base}/preguntar`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ caso: '' }) })
    assert.equal(mala.status, 400)
  })
})
