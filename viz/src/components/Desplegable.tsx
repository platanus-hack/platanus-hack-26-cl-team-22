import { useEffect, useId, useRef, useState } from 'react'

export interface Opcion {
  id: string
  titulo: string
  /** una línea que explica la opción */
  detalle?: string
}

/** Lista desplegable propia: el botón muestra la opción elegida y la lista explica cada una. */
export function Desplegable({ etiqueta, opciones, valor, onCambiar }: { etiqueta: string; opciones: Opcion[]; valor: string | undefined; onCambiar: (id: string) => void }) {
  const [abierto, setAbierto] = useState(false)
  const raiz = useRef<HTMLDivElement>(null)
  const id = useId()
  const actual = opciones.find((o) => o.id === valor) ?? opciones[0]

  useEffect(() => {
    if (!abierto) return
    const fuera = (e: PointerEvent) => {
      if (!raiz.current?.contains(e.target as Node)) setAbierto(false)
    }
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAbierto(false)
    }
    window.addEventListener('pointerdown', fuera)
    window.addEventListener('keydown', tecla)
    return () => {
      window.removeEventListener('pointerdown', fuera)
      window.removeEventListener('keydown', tecla)
    }
  }, [abierto])

  return (
    <div className="desplegable" ref={raiz}>
      <span className="desplegable-etiqueta" id={`${id}-e`}>
        {etiqueta}
      </span>
      <button type="button" className="desplegable-boton" aria-haspopup="listbox" aria-expanded={abierto} aria-labelledby={`${id}-e ${id}-v`} onClick={() => setAbierto((x) => !x)}>
        <span id={`${id}-v`}>{actual?.titulo}</span>
        <svg viewBox="0 0 12 8" aria-hidden="true">
          <path d="M1 1.5 L6 6.5 L11 1.5" />
        </svg>
      </button>
      {abierto && (
        <ul className="desplegable-lista" role="listbox" aria-labelledby={`${id}-e`}>
          {opciones.map((o) => (
            <li key={o.id} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={o.id === actual?.id}
                className="desplegable-opcion"
                onClick={() => {
                  onCambiar(o.id)
                  setAbierto(false)
                }}
              >
                <b>{o.titulo}</b>
                {o.detalle && <span>{o.detalle}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
