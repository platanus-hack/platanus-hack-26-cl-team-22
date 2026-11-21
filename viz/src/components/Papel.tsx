import type { ReactNode } from 'react'
import type { Estado, Veredicto } from '../lib/estado'
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
export function Muestra({ clase, forma = 'cuadro' }: { clase: string; forma?: 'cuadro' | 'feston' | 'trama' | 'pila' | 'disco' }) {
  if (forma === 'trama')
    return (
      <svg className="muestra" viewBox="0 0 24 24" aria-hidden="true">
        <rect x="1.5" y="1.5" width="21" height="21" className={clase} />
        <path d="M2 12 L12 2 M2 22 L22 2 M12 22 L22 12" className="muestra-trama" />
      </svg>
    )
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

export interface Cifra {
  etiqueta: string
  valor: string
  /** línea corta bajo el valor (banda, sentido) */
  nota?: string
  /** 'mejora' o 'empeora' tiñen el valor */
  tono?: 'mejora' | 'empeora'
}

/** Fila de cifras clave: el dato grande, su etiqueta arriba y una nota corta abajo. */
export function Cifras({ items, unidad }: { items: Cifra[]; unidad?: string }) {
  return (
    <dl className="cifras" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
      {items.map((c) => (
        <div className="cifra" key={c.etiqueta}>
          <dt>{c.etiqueta}</dt>
          <dd className={c.tono ? `cifra-${c.tono}` : undefined}>
            {c.valor}
            {unidad && <small> {unidad}</small>}
          </dd>
          {c.nota && <dd className="cifra-nota">{c.nota}</dd>}
        </div>
      ))}
    </dl>
  )
}

/** Clave del gráfico con muestras en vez de frases. */
export function ClaveGrafico({ nivelBanda, comparacion }: { nivelBanda: number | null; comparacion?: string }) {
  return (
    <p className="clave-grafico" aria-hidden="true">
      <span>
        <i className="clave-linea" /> mediana
      </span>
      <span>
        <i className={`clave-banda ${nivelBanda !== null && nivelBanda >= 2 ? 'nivel-1' : 'nivel-0'}`} /> banda p10–p90
      </span>
      {comparacion && (
        <span>
          <i className="clave-trazos" /> {comparacion}
        </span>
      )}
    </p>
  )
}

export interface Etiqueta {
  titulo: string
  /** dato principal de la comuna, ya formateado */
  valor?: string
  unidad?: string
  /** clase de papel del dato (nivel-3, mejora-2, zona-a…) */
  clase?: string
  /** veredicto frente a la norma, si aplica */
  estado?: { id: Estado; texto: string }
  lineas: string[]
}

/** Veredicto directo: el sello de color dice el estado y al lado va el porqué. */
export function Sello({ v, futuro = true }: { v: Veredicto; futuro?: boolean }) {
  return (
    <div className="veredicto">
      <p className="veredicto-fila">
        <b className={`sello sello-${v.estado}`}>{v.titulo}</b>
        <span>{v.razon}</span>
      </p>
      {futuro && v.futuro && <p className="veredicto-futuro">{v.futuro}</p>}
    </div>
  )
}

/** Tarjeta que sigue al puntero sobre el mapa: nombre, dato grande con su color y hasta dos líneas. */
export function TarjetaMapa({ e, x, y, ancho }: { e: Etiqueta; x: number; y: number; ancho: number }) {
  return (
    <div className="tag-mapa" role="tooltip" style={{ left: x + 18, top: y + 18, transform: x > ancho * 0.62 ? 'translateX(calc(-100% - 36px))' : undefined }}>
      <b>{e.titulo}</b>
      {e.estado && <span className={`sello sello-${e.estado.id}`}>{e.estado.texto}</span>}
      {e.valor && (
        <span className="tag-valor">
          {e.clase && <i className={`tag-muestra ${e.clase}`} />}
          <strong>{e.valor}</strong>
          {e.unidad && <small>{e.unidad}</small>}
        </span>
      )}
      {e.lineas.map((l, i) => (
        <span className="tag-linea" key={i}>
          {l}
        </span>
      ))}
    </div>
  )
}
