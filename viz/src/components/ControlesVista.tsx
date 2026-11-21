import type { Encuadre } from './MapaComunas'

export type ModoMapa = 'valor' | 'diferencia'

interface Props {
  encuadre: Encuadre
  onEncuadre: (e: Encuadre) => void
  onReiniciar: () => void
  modo: ModoMapa
  onModo: (m: ModoMapa) => void
  /** false si el escenario activo es el de referencia: no hay con qué comparar */
  puedeDiferencia: boolean
  baseNombre: string | undefined
}

/** Controles sobre el mapa: encuadre, restablecer vista y qué se pinta (valor o diferencia). */
export function ControlesVista({ encuadre, onEncuadre, onReiniciar, modo, onModo, puedeDiferencia, baseNombre }: Props) {
  return (
    <div className="vista-controles">
      <div className="vista-fila">
        <div className="segmentado" role="group" aria-label="Encuadre del mapa">
          <button type="button" aria-pressed={encuadre === 'gran-santiago'} onClick={() => onEncuadre('gran-santiago')}>
            Gran Santiago
          </button>
          <button type="button" aria-pressed={encuadre === 'region'} onClick={() => onEncuadre('region')}>
            Toda la región
          </button>
        </div>
        <button type="button" className="boton" onClick={onReiniciar}>
          Restablecer vista
        </button>
      </div>
      <div className="vista-fila">
        <div className="segmentado" role="group" aria-label="Qué se pinta en el mapa">
          <button type="button" aria-pressed={modo === 'valor' || !puedeDiferencia} onClick={() => onModo('valor')}>
            Valor
          </button>
          <button
            type="button"
            aria-pressed={modo === 'diferencia' && puedeDiferencia}
            disabled={!puedeDiferencia}
            onClick={() => onModo('diferencia')}
          >
            Diferencia frente a todos los planes
          </button>
        </div>
      </div>
      {!puedeDiferencia && (
        <p className="vista-nota">
          Apaga una política para ver cuánto cambia cada comuna frente a &laquo;{baseNombre ?? 'todos los planes'}&raquo;.
        </p>
      )}
    </div>
  )
}
