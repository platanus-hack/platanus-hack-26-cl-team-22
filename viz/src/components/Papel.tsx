import type { ReactNode } from 'react'
import { rutaRodela } from '../lib/feston'

/**
 * Rodela de papel: un disco festoneado de borde, un filo blanco y el disco del nivel encima.
 * El borde toma el color del nivel vecino cuando la banda lo alcanza; si no, es de tinta.
 */
export function Rodela({ nivel, borde, children, etiqueta }: { nivel: number | null; borde: number | null; children: ReactNode; etiqueta: string }) {
  return (
    <div className={`rodela${nivel === null ? ' rodela-sin-dato' : ` txt-nivel-${nivel}`}`} role="img" aria-label={etiqueta}>
      <svg viewBox="0 0 200 200" aria-hidden="true">
        <path d={rutaRodela(100, 100, 92, 24)} className="alzado-sombra" transform="translate(1.5 1.5)" />
        <path d={rutaRodela(100, 100, 92, 24)} className={borde === null ? 'rodela-borde-tinta' : `nivel-${borde}`} />
        <circle cx="100" cy="100" r="78" className="rodela-filo" />
        <circle cx="100" cy="100" r="73" className={nivel === null ? 'rodela-vacia' : `nivel-${nivel}`} />
      </svg>
      <span className="rodela-contenido">{children}</span>
    </div>
  )
}

/** Muestra plana de papel para leyendas. */
export function Muestra({ clase, forma = 'cuadro' }: { clase: string; forma?: 'cuadro' | 'feston' | 'pila' | 'disco' }) {
  if (forma === 'feston')
    return (
      <svg className="muestra" viewBox="0 0 24 24" aria-hidden="true">
        <rect x="1" y="1" width="22" height="22" className="nivel-3" />
        <path d={rutaRodela(12, 12, 7.5, 9)} className={clase} />
      </svg>
    )
  if (forma === 'pila')
    return (
      <svg className="muestra" viewBox="0 0 24 24" aria-hidden="true">
        <rect x="7" y="7" width="15" height="15" className="pol-1" />
        <rect x="4.5" y="4.5" width="15" height="15" className={clase} />
        <rect x="1.5" y="1.5" width="15" height="15" className="nivel-2" />
      </svg>
    )
  if (forma === 'disco')
    return (
      <svg className="muestra" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="9" className={clase} />
      </svg>
    )
  return (
    <svg className="muestra" viewBox="0 0 24 24" preserveAspectRatio="none" aria-hidden="true">
      <rect x="1.5" y="1.5" width="21" height="21" className={clase} />
    </svg>
  )
}

export function IconoJugar({ jugando }: { jugando: boolean }) {
  return (
    <svg viewBox="0 0 20 20" className="icono" aria-hidden="true">
      {jugando ? (
        <>
          <rect x="4" y="3.5" width="4.2" height="13" />
          <rect x="11.8" y="3.5" width="4.2" height="13" />
        </>
      ) : (
        <path d="M5 3.2 L16.5 10 L5 16.8 Z" />
      )}
    </svg>
  )
}
