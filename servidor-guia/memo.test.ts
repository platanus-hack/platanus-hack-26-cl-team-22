import assert from 'node:assert/strict'
import { test } from 'node:test'
import { crearMemo } from './memo.ts'

const vivo = () => new AbortController().signal

test('keeps successful results until they expire, and evicts the oldest past the size cap', async () => {
  let t = 0
  const m = crearMemo<string>(1000, 2, () => t)
  await m.calcular('a', async () => 'A', vivo())
  await m.calcular('b', async () => 'B', vivo())
  assert.equal(m.leer('a'), 'A')
  await m.calcular('c', async () => 'C', vivo())
  assert.equal(m.leer('a'), undefined)
  assert.equal(m.leer('c'), 'C')
  t = 1000
  assert.equal(m.leer('c'), undefined)
})

test('null results are not kept', async () => {
  const m = crearMemo<string>(1000, 10)
  assert.equal(await m.calcular('a', async () => null, vivo()), null)
  assert.equal(m.leer('a'), undefined)
})

test('the shared call is cancelled only when every waiting request has gone away', async () => {
  const m = crearMemo<string>(1000, 10)
  let senal: AbortSignal | null = null
  const f = (s: AbortSignal) => {
    senal = s
    return new Promise<string | null>((ok) => s.addEventListener('abort', () => ok(null)))
  }
  const uno = new AbortController()
  const dos = new AbortController()
  const p1 = m.calcular('k', f, uno.signal)
  const p2 = m.calcular('k', f, dos.signal)
  uno.abort()
  assert.equal(senal!.aborted, false)
  dos.abort()
  assert.equal(senal!.aborted, true)
  assert.deepEqual(await Promise.all([p1, p2]), [null, null])
})
