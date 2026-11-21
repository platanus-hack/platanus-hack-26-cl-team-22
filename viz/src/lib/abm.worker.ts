/// <reference lib="webworker" />
/**
 * Runs the agent-based moves simulation off the main thread (viz/README.md: browser simulations
 * live in a Web Worker). Receives parameters and options, returns the runs.
 */
import { simularReplicas, type OpcionesAbm, type ParametrosAbm } from './mudanzasAbm'

export interface PedidoAbm {
  id: number
  params: ParametrosAbm
  opciones: OpcionesAbm
  replicas: number
}

self.onmessage = (e: MessageEvent<PedidoAbm>) => {
  const { id, params, opciones, replicas } = e.data
  const r = simularReplicas(params, opciones, replicas)
  self.postMessage({ id, total: r.total, corridas: r.corridas })
}
