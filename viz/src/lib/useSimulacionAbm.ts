import { useEffect, useRef, useState } from 'react'
import { simularReplicas, type OpcionesAbm, type ParametrosAbm, type ResultadoAbm } from './mudanzasAbm'
import type { PedidoAbm } from './abm.worker'

export interface SimulacionAbm {
  total: { p10: number[]; p50: number[]; p90: number[] }
  corridas: ResultadoAbm[]
}

export const REPLICAS_ABM = 20

/**
 * Runs `REPLICAS_ABM` runs of the moves simulation whenever the options change, in a Web Worker.
 * If the browser cannot start the worker, it runs fewer replicas on the main thread.
 */
export function useSimulacionAbm(params: ParametrosAbm | null, opciones: OpcionesAbm) {
  const [resultado, setResultado] = useState<SimulacionAbm | null>(null)
  const [calculando, setCalculando] = useState(false)
  const worker = useRef<Worker | null>(null)
  const ultimo = useRef(0)
  const clave = JSON.stringify(opciones)

  useEffect(() => {
    try {
      worker.current = new Worker(new URL('./abm.worker.ts', import.meta.url), { type: 'module' })
      worker.current.onmessage = (e: MessageEvent<SimulacionAbm & { id: number }>) => {
        if (e.data.id !== ultimo.current) return
        setResultado({ total: e.data.total, corridas: e.data.corridas })
        setCalculando(false)
      }
    } catch {
      worker.current = null
    }
    return () => worker.current?.terminate()
  }, [])

  useEffect(() => {
    if (!params) return
    const id = ++ultimo.current
    setCalculando(true)
    if (worker.current) {
      const pedido: PedidoAbm = { id, params, opciones, replicas: REPLICAS_ABM }
      worker.current.postMessage(pedido)
      return
    }
    const r = simularReplicas(params, opciones, 6)
    setResultado({ total: r.total, corridas: r.corridas })
    setCalculando(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, clave])

  return { resultado, calculando }
}
