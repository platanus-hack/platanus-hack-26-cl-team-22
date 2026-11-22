import assert from 'node:assert/strict'
import { test } from 'node:test'
import { MODELO, interpretarCaso, prepararPreguntas, validarPedidoPreguntas, redactarGuia, validarPedidoCaso, validarPedidoGuia, type ClienteClaude } from './claude.ts'

/** Fake Claude client: records the request and answers with a fixed response. */
function falso(respuesta: { stop_reason?: string; texto?: string }) {
  const pedidos: Record<string, unknown>[] = []
  const cliente: ClienteClaude = {
    beta: {
      messages: {
        create: async (p: Record<string, unknown>) => {
          pedidos.push(p)
          return {
            stop_reason: respuesta.stop_reason ?? 'end_turn',
            content: respuesta.texto === undefined ? [] : [{ type: 'text', text: respuesta.texto }],
          }
        },
      },
    },
  }
  return { cliente, pedidos }
}

const pedido = {
  caso: 'Busco departamento para mi familia; mi hijo tiene asma.',
  perfil: 'Comprar una vivienda',
  prioridades: { pm25_anual: 8, seguridad: 8, crecimiento_poblacion: 3 },
}

test('interpretarCaso asks Claude for strict JSON with the closed schema, low effort and refusal fallbacks', async () => {
  const { cliente, pedidos } = falso({ texto: JSON.stringify({ ajustes: [], indicadores: [], no_medido: [] }) })
  await interpretarCaso(cliente, pedido)
  const p = pedidos[0] as Record<string, any>
  assert.equal(p.model, MODELO)
  assert.equal(MODELO, 'claude-sonnet-5-5')
  assert.equal(p.output_config.effort, 'low')
  assert.equal(p.output_config.format.type, 'json_schema')
  assert.deepEqual(p.output_config.format.schema.required, ['ajustes', 'indicadores', 'no_medido'])
  assert.equal(p.fallbacks, 'default')
  assert.deepEqual(p.betas, ['server-side-fallback-2026-07-01'])
  assert.equal(p.system[0].cache_control.type, 'ephemeral')
  assert.match(p.messages[0].content, /mi hijo tiene asma/)
})

test('interpretarCaso keeps only catalog values quoted from the case', async () => {
  const { cliente } = falso({
    texto: JSON.stringify({
      ajustes: [
        { variable: 'pm25_anual', grado: 10, cita: 'mi hijo tiene asma' },
        { variable: 'seguridad', grado: 10, cita: 'vivo en una zona peligrosa' },
      ],
      indicadores: ['dias_sobre_norma_diaria_pm25'],
      no_medido: [],
    }),
  })
  const r = await interpretarCaso(cliente, pedido)
  assert.deepEqual(r?.ajustes, [{ variable: 'pm25_anual', grado: 10, cita: 'mi hijo tiene asma' }])
  assert.deepEqual(r?.indicadores, ['dias_sobre_norma_diaria_pm25'])
})

test('interpretarCaso returns null on a refusal or on text that is not JSON', async () => {
  assert.equal(await interpretarCaso(falso({ stop_reason: 'refusal' }).cliente, pedido), null)
  assert.equal(await interpretarCaso(falso({ texto: 'no es json' }).cliente, pedido), null)
})

test('validarPedidoCaso rejects empty or oversized cases and bad priorities', () => {
  assert.equal(validarPedidoCaso({ ...pedido, caso: '   ' }), null)
  assert.equal(validarPedidoCaso({ ...pedido, caso: 'x'.repeat(801) }), null)
  assert.equal(validarPedidoCaso({ ...pedido, prioridades: 'alta' }), null)
  assert.equal(validarPedidoCaso('hola'), null)
  assert.deepEqual(validarPedidoCaso(pedido), pedido)
})

test('redactarGuia returns one capped paragraph from the model', async () => {
  const { cliente, pedidos } = falso({ texto: 'María Pinto encabeza.\n\nLe siguen Alhué y San Pedro. ' + 'x'.repeat(700) })
  const g = await redactarGuia(cliente, {
    perfil: 'Comprar una vivienda',
    contexto: pedido.caso,
    prioridades: { Aire: 10 },
    anio: 2026,
    top: [],
  })
  assert.ok(g && g.texto.length <= 600 && !g.texto.includes('\n'))
  assert.equal((pedidos[0] as Record<string, any>).model, MODELO)
})

test('validarPedidoGuia accepts the page contract and rejects anything else', () => {
  const ok = { perfil: 'Comprar una vivienda', contexto: 'mi hijo tiene asma', prioridades: { Aire: 10 }, anio: 2026, top: [] }
  assert.deepEqual(validarPedidoGuia(ok), ok)
  assert.equal(validarPedidoGuia({ cualquier: 'cosa' }), null)
  assert.equal(validarPedidoGuia({ ...ok, contexto: 'x'.repeat(900) }), null)
  assert.equal(validarPedidoGuia({ ...ok, top: [{ comuna: 'A', riesgo: 'alto', variables: [] }] }), null)
})

test('redactarGuia discards a guide cut by max_tokens', async () => {
  const { cliente } = falso({ stop_reason: 'max_tokens', texto: 'María Pinto encabeza porque' })
  assert.equal(await redactarGuia(cliente, { perfil: 'x', contexto: 'y', prioridades: {}, anio: 2026, top: [] }), null)
})

test('prepararPreguntas asks for strict JSON, caps the questions at two and treats refusals as nothing', async () => {
  const { cliente, pedidos } = falso({ texto: JSON.stringify({ preguntas: ['¿Es para vivir o para una empresa?', '¿Hay niños o personas con asma?', '¿Una tercera pregunta?'] }) })
  const q = await prepararPreguntas(cliente, { caso: 'Quiero evaluar el aire' })
  assert.equal(q?.length, 2)
  const p = pedidos[0] as Record<string, any>
  assert.equal(p.model, MODELO)
  assert.equal(p.output_config.format.type, 'json_schema')
  assert.match(p.messages[0].content, /Quiero evaluar el aire/)
  assert.equal(await prepararPreguntas(falso({ stop_reason: 'refusal' }).cliente, { caso: 'x' }), null)
  assert.equal(await prepararPreguntas(falso({ texto: 'no es json' }).cliente, { caso: 'x' }), null)
  assert.deepEqual(await prepararPreguntas(falso({ texto: JSON.stringify({ preguntas: [] }) }).cliente, { caso: 'x' }), [])
})

test('validarPedidoPreguntas only accepts a non-empty case within the limit', () => {
  assert.deepEqual(validarPedidoPreguntas({ caso: ' Busco casa ' }), { caso: 'Busco casa' })
  assert.equal(validarPedidoPreguntas({ caso: '' }), null)
  assert.equal(validarPedidoPreguntas({ caso: 'x'.repeat(801) }), null)
  assert.equal(validarPedidoPreguntas(null), null)
})
