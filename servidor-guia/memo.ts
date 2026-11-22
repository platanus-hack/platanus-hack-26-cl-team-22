/**
 * Response cache for the model routes: identical requests (the example chips, a reload, the same case
 * read twice) are answered from memory instead of paying for another call.
 *
 * - Only successful results are kept, for `ttlMs`, at most `max` entries (oldest out first).
 * - Identical requests that arrive while the first is still running share that one call.
 * - The shared call is cancelled only when every request waiting on it has gone away.
 */
export interface Memo<T> {
  /** The cached result, or undefined when there is none (or it expired). */
  leer(clave: string): T | undefined
  /** Runs `f` once per key at a time; a non-null result is cached. */
  calcular(clave: string, f: (signal: AbortSignal) => Promise<T | null>, signal: AbortSignal): Promise<T | null>
}

export function crearMemo<T>(ttlMs: number, max: number, ahora: () => number = Date.now): Memo<T> {
  const hechos = new Map<string, { hasta: number; valor: T }>()
  const enVuelo = new Map<string, { promesa: Promise<T | null>; corte: AbortController; esperando: number }>()

  const guardar = (clave: string, valor: T) => {
    hechos.delete(clave)
    hechos.set(clave, { hasta: ahora() + ttlMs, valor })
    while (hechos.size > max) hechos.delete(hechos.keys().next().value!)
  }

  return {
    leer(clave) {
      const e = hechos.get(clave)
      if (!e) return undefined
      if (e.hasta <= ahora()) {
        hechos.delete(clave)
        return undefined
      }
      return e.valor
    },
    async calcular(clave, f, signal) {
      let v = enVuelo.get(clave)
      if (!v) {
        const corte = new AbortController()
        const promesa = f(corte.signal)
          .then((r) => {
            if (r !== null) guardar(clave, r)
            return r
          })
          .finally(() => {
            if (enVuelo.get(clave) === v) enVuelo.delete(clave)
          })
        v = { promesa, corte, esperando: 0 }
        enVuelo.set(clave, v)
      }
      const vuelo = v
      vuelo.esperando++
      const salir = () => {
        if (--vuelo.esperando > 0) return
        vuelo.corte.abort()
        // A request arriving now must start a fresh call, not join the cancelled one.
        if (enVuelo.get(clave) === vuelo) enVuelo.delete(clave)
      }
      if (signal.aborted) salir()
      else signal.addEventListener('abort', salir, { once: true })
      try {
        return await vuelo.promesa
      } finally {
        signal.removeEventListener('abort', salir)
      }
    },
  }
}
