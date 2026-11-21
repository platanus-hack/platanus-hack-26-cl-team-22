import type { CSSProperties } from 'react'
import { PAPELES_POLITICA } from '../lib/capas'
import { fmtPct } from '../lib/format'
import type { Comuna, Politica } from '../lib/types'

const NIVELES: Record<string, string> = { regional: 'Regional', comunal: 'Comunal', proyecto: 'Proyecto' }
const TIPOS = ['vigente', 'propuesta', 'ilustrativa']

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

const pct = (x: number) => `${Math.min(1, Math.max(0, x)) * 100}%`

/**
 * Una política como fila con interruptor: casilla del color de la política, nombre y alcance en tinta,
 * y a la derecha la probabilidad de que se cumpla con su rango p10–p90 en una regla corta.
 */
export function TiraPolitica({ politica: p, indice, tecla, pegada, comunas, onAlternar }: Props) {
  const c = p.credibilidad
  const nivel = NIVELES[p.nivel] ?? (typeof p.nivel === 'string' ? p.nivel : '')
  const tipo = p.tipo && TIPOS.includes(p.tipo) ? p.tipo : ''
  // el tipo ya va en la línea de abajo: no se repite entre paréntesis en el nombre
  const nombre = p.nombre.replace(/\s*\((propuesta|ilustrativa)\)\s*$/i, '')
  const estilo = { '--c': `var(--pol-${indice % PAPELES_POLITICA})` } as CSSProperties
  return (
    <button
      type="button"
      className={`plan-item${pegada ? '' : ' plan-item-apagada'}`}
      style={estilo}
      aria-pressed={pegada}
      aria-label={`${nombre}. Se cumple con probabilidad ${fmtPct(c.media)}, entre ${fmtPct(c.p10)} y ${fmtPct(c.p90)}`}
      aria-keyshortcuts={tecla?.toUpperCase()}
      onClick={onAlternar}
    >
      <span className="plan-caja" aria-hidden="true">
        {pegada && (
          <svg viewBox="0 0 16 16">
            <path d="M3 8.5 L6.6 12 L13 4.5" />
          </svg>
        )}
      </span>
      <span className="plan-txt">
        <b>{nombre}</b>
        <small>{[nivel, alcance(p, comunas), tipo, pegada ? '' : 'apagada'].filter(Boolean).join(' · ')}</small>
      </span>
      <span className="plan-cred" aria-hidden="true">
        <b>{fmtPct(c.media)}</b>
        <span className="plan-rango">
          <i style={{ left: pct(c.p10), width: `calc(${pct(c.p90)} - ${pct(c.p10)})` }} />
          <u style={{ left: pct(c.media) }} />
        </span>
      </span>
      {tecla && <kbd className="plan-tecla">{tecla.toUpperCase()}</kbd>}
    </button>
  )
}
