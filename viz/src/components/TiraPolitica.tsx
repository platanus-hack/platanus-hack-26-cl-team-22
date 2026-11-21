import type { CSSProperties } from 'react'
import { PAPELES_POLITICA } from '../lib/capas'
import { fmtPct } from '../lib/format'
import type { Comuna, Politica } from '../lib/types'

const NIVELES: Record<string, string> = { regional: 'Regional', comunal: 'Comunal', proyecto: 'Proyecto' }

export function alcance(p: Politica, comunas: Comuna[]): string {
  if (p.comunas === 'todas') return 'todas las comunas'
  const nombres = p.comunas.map((c) => comunas.find((x) => x.codigo === c)?.nombre ?? c)
  if (nombres.length === 0) return 'sin comunas'
  return nombres.length <= 3 ? nombres.join(', ') : `${nombres.length} comunas`
}

interface Props {
  politica: Politica
  indice: number
  tecla: string | undefined
  pegada: boolean
  comunas: Comuna[]
  onAlternar: () => void
}

/**
 * Una política como tira de papel frío. La franja inferior muestra cuánto de la tira está pegado
 * (credibilidad media), con muescas de tijera en p10 y p90. Despegada, la tira se levanta y muestra su revés blanco.
 */
export function TiraPolitica({ politica: p, indice, tecla, pegada, comunas, onAlternar }: Props) {
  const c = p.credibilidad
  const papel = indice % PAPELES_POLITICA
  const giro = ((indice * 37) % 5) - 2
  const nivel = NIVELES[p.nivel] ?? (typeof p.nivel === 'string' ? p.nivel : '')
  const propuesta = p.tipo === 'propuesta'
  const estilo = {
    '--giro': `${giro * 0.45}deg`,
    '--c': `var(--pol-${papel})`,
    '--c-txt': `var(--pol-txt-${papel})`,
    '--media': `${Math.min(1, Math.max(0, c.media)) * 100}%`,
    '--p10': `${Math.min(1, Math.max(0, c.p10)) * 100}%`,
    '--p90': `${Math.min(1, Math.max(0, c.p90)) * 100}%`,
  } as CSSProperties
  const probabilidad = `Se cumple con probabilidad ${fmtPct(c.media)} (${fmtPct(c.p10)}–${fmtPct(c.p90)})`
  const cara = (
    <>
      <span className="tira-cab">
        {tecla && <kbd className="tira-tecla">{tecla.toUpperCase()}</kbd>}
        <span className="tira-nombre">{p.nombre}</span>
      </span>
      <span className="tira-cred">
        {[nivel, alcance(p, comunas), propuesta ? 'propuesta' : p.tipo === 'vigente' ? 'vigente' : ''].filter(Boolean).join(' · ')}. {probabilidad}
        {!pegada && <b> · {propuesta ? 'no está en el plan: pégala para probarla' : 'despegada: ya no avanza'}</b>}
      </span>
    </>
  )
  return (
    <button
      type="button"
      className={`tira ${pegada ? 'pegada' : 'despegada'}`}
      style={estilo}
      aria-pressed={pegada}
      onClick={onAlternar}
      aria-keyshortcuts={tecla?.toUpperCase()}
    >
      {/* La parte pegada (credibilidad media) es el papel macizo; el resto está levantado y se ve más pálido */}
      <span className="tira-fondo" aria-hidden="true">
        <span className="tira-maciza" />
        <span className="tira-pliegue" />
        <span className="tira-marca" style={{ left: 'var(--p10)' }} />
        <span className="tira-marca" style={{ left: 'var(--p90)' }} />
      </span>
      <span className="tira-cara">{cara}</span>
      {/* Mismo texto en el color claro, recortado a la parte maciza: el contraste se mantiene en las dos partes */}
      <span className="tira-cara tira-cara-clara" aria-hidden="true">
        {cara}
      </span>
    </button>
  )
}
