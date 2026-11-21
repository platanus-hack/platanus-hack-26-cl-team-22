import { fmt } from '../lib/format'
import type { TipoHogar, Variable } from '../lib/types'

interface Props {
  tipos: TipoHogar[]
  variables: Variable[]
  /** ids de variable que tienen datos */
  conDato: ReadonlySet<string>
  perfilId: string
  pesos: Record<string, number>
  onPerfil: (id: string) => void
  onPeso: (variable: string, valor: number) => void
}

export const PERSONALIZADO = '__personalizado'

export function nombreVariable(id: string, variables: Variable[]): string {
  const v = variables.find((x) => x.id === id)
  if (v) return v.nombre
  const t = id.replace(/_/g, ' ')
  return t.charAt(0).toUpperCase() + t.slice(1)
}

export function PerfilHogar({ tipos, variables, conDato, perfilId, pesos, onPerfil, onPeso }: Props) {
  const claves = [...new Set([...tipos.flatMap((t) => Object.keys(t.pesos)), ...conDato])]

  return (
    <div className="perfil" role="group" aria-label="Perfil del hogar">
      <div className="perfil-sel">
        <label className="caps" htmlFor="perfil-hogar">
          Perfil del hogar
        </label>
        <select id="perfil-hogar" value={perfilId} onChange={(e) => onPerfil(e.target.value)}>
          {tipos.map((t) => (
            <option key={t.id} value={t.id}>
              {t.nombre}
            </option>
          ))}
          <option value={PERSONALIZADO}>Personalizado</option>
        </select>
      </div>
      <div className="pesos">
        {claves.map((k) => {
          const hay = conDato.has(k)
          return (
            <div className={`peso${hay ? '' : ' sin-dato'}`} key={k}>
              <label htmlFor={`peso-${k}`}>
                <span>{nombreVariable(k, variables)}</span>
                <span className="num">{hay ? fmt(pesos[k] ?? 0, 2) : 'sin dato'}</span>
              </label>
              <input
                id={`peso-${k}`}
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={pesos[k] ?? 0}
                disabled={!hay}
                onChange={(e) => onPeso(k, Number(e.target.value))}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}
