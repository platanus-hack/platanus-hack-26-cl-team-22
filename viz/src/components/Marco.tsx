import { fmt, fmtSigned } from '../lib/format'
import type { Lena } from '../lib/lena'
import { bordesPasos, papelNivel, textoNivel } from '../lib/niveles'
import type { Variable } from '../lib/types'
import type { Encuadre, ModoMapa } from './MapaPapel'
import { IconoJugar, Muestra } from './Papel'

interface LeyendaProps {
  modo: ModoMapa
  variable: Variable
  cortes: readonly number[]
  norma: number | null
  difMax: number
  baseNombre?: string
  lena: Lena | null
  hayPiezas: boolean
}

export function Leyenda(p: LeyendaProps) {
  const u = p.variable.unidad
  if (p.modo === 'lena') {
    const tMax = Math.max(0, ...(p.lena?.comunas.map((c) => c.toneladas ?? 0) ?? [0]))
    return (
      <div className="leyenda" aria-label="Leyenda del mapa">
        <p className="leyenda-titulo">Leña, RETC {p.lena?.anio || 2023}</p>
        <ul>
          <li>
            <Muestra clase="zona-a" /> Zona A: leña prohibida (art. 74)
          </li>
          <li>
            <Muestra clase="zona-b" /> Zona B: solo calefactores nuevos (art. 75)
          </li>
          <li>
            <Muestra clase="disco" forma="disco" /> Disco: área según toneladas (el mayor, {fmt(tMax, 0)} t)
          </li>
          <li>
            <Muestra clase="disco-sin-dato" forma="disco" /> Sin dato en el RETC
          </li>
        </ul>
      </div>
    )
  }
  if (p.modo === 'diferencia') {
    const b = bordesPasos(p.difMax)
    const r = (i: number, s: string) => `${s}${fmt(b[i]!, 1)} a ${s}${fmt(b[i + 1]!, 1)}`
    return (
      <div className="leyenda" aria-label="Leyenda del mapa">
        <p className="leyenda-titulo">
          Diferencia de mediana frente a «{p.baseNombre}», {u}
        </p>
        <ul className="leyenda-dif">
          <li>
            <Muestra clase="mejora-3" /> mejora {r(2, '−')}
          </li>
          <li>
            <Muestra clase="mejora-2" /> mejora {r(1, '−')}
          </li>
          <li>
            <Muestra clase="mejora-1" /> mejora {r(0, '−')}
          </li>
          <li>
            <Muestra clase="dif-0" /> sin cambio (menos de {fmtSigned(b[0]!).replace('+', '±')})
          </li>
          <li>
            <Muestra clase="empeora-1" /> empeora {r(0, '+')}
          </li>
          <li>
            <Muestra clase="empeora-2" /> empeora {r(1, '+')}
          </li>
          <li>
            <Muestra clase="empeora-3" /> empeora {r(2, '+')}
          </li>
        </ul>
      </div>
    )
  }
  return (
    <div className="leyenda" aria-label="Leyenda del mapa">
      <p className="leyenda-titulo">
        {p.variable.nombre}, {u}
      </p>
      <ul className="leyenda-niveles" style={{ gridTemplateColumns: `repeat(${p.cortes.length + 1}, auto)` }}>
        {Array.from({ length: p.cortes.length + 1 }, (_, i) => (
          <li key={i} className={p.norma !== null && p.cortes[i - 1] === p.norma ? 'tras-norma' : undefined}>
            {p.norma !== null && p.cortes[i - 1] === p.norma && (
              <span className="marca-norma" aria-hidden="true">
                norma anual {fmt(p.norma, Number.isInteger(p.norma) ? 0 : 1)}
              </span>
            )}
            <Muestra clase={`nivel-${papelNivel(i, p.cortes)}`} /> {textoNivel(i, p.cortes)}
          </li>
        ))}
      </ul>
      <ul>
        <li>
          <Muestra clase="sin-dato" /> Sin dato
        </li>
        <li className="solo-plano">
          <Muestra clase="nivel-2" forma="feston" /> Festón: la banda p10–p90 alcanza otro nivel
        </li>
        <li className="solo-relieve">
          <Muestra clase="nivel-3" forma="trama" /> Trama: la banda p10–p90 alcanza otro nivel
        </li>
        {p.hayPiezas && (
          <li className="solo-plano">
            <Muestra clase="pol-0" forma="pila" /> Canto frío en la comuna elegida: cada plan pegado, más ancho cuanto más aporta
          </li>
        )}
      </ul>
      <p className="leyenda-nota">
        Cortes: referencia provisional{p.norma !== null ? `, relativos a la norma anual de ${fmt(p.norma, Number.isInteger(p.norma) ? 0 : 1)} ${u}` : ''}.
      </p>
    </div>
  )
}

interface ControlesProps {
  encuadre: Encuadre
  onEncuadre: (e: Encuadre) => void
  onReencuadrar: () => void
  diferencia: { activa: boolean; base: string; onCambiar: (v: boolean) => void } | null
}

export function ControlesMapa({ encuadre, onEncuadre, onReencuadrar, diferencia }: ControlesProps) {
  return (
    <div className="controles-mapa">
      <div className="controles-fila" role="group" aria-label="Encuadre del mapa">
      <button type="button" className="pestana-mapa" aria-pressed={encuadre === 'gran-santiago'} onClick={() => onEncuadre('gran-santiago')}>
        Gran Santiago
      </button>
      <button type="button" className="pestana-mapa" aria-pressed={encuadre === 'region'} onClick={() => onEncuadre('region')}>
        Toda la región
      </button>
      <button type="button" className="pestana-mapa" onClick={onReencuadrar} aria-keyshortcuts="0">
        Reencuadrar
      </button>
      </div>
      {diferencia && (
        <div className="controles-fila" role="radiogroup" aria-label="Qué muestra el mapa">
          <button type="button" role="radio" aria-checked={!diferencia.activa} className="pestana-mapa" onClick={() => diferencia.onCambiar(false)}>
            Valor
          </button>
          <button type="button" role="radio" aria-checked={diferencia.activa} className="pestana-mapa" onClick={() => diferencia.onCambiar(true)} aria-keyshortcuts="D">
            Diferencia frente a «{diferencia.base}» <kbd>D</kbd>
          </button>
        </div>
      )}
    </div>
  )
}

interface AniosProps {
  anios: number[]
  idx: number
  jugando: boolean
  onIdx: (i: number) => void
  onJugar: (v: boolean) => void
  escenario: string
}

export function Anios({ anios, idx, jugando, onIdx, onJugar, escenario }: AniosProps) {
  return (
    <div className="anios">
      <button type="button" className="jugar" onClick={() => onJugar(!jugando)} aria-label={jugando ? 'Pausar' : 'Reproducir los años'} aria-keyshortcuts="Space">
        <IconoJugar jugando={jugando} />
      </button>
      <div className="anios-pestanas" role="tablist" aria-label="Año">
        {anios.map((a, i) => (
          <button key={a} type="button" role="tab" aria-selected={i === idx} className="anio" onClick={() => onIdx(i)}>
            {a}
          </button>
        ))}
      </div>
      <p className="anios-pie">
        <span>{escenario}</span>
        <span className="anios-teclas">Flechas: año · espacio: reproducir</span>
      </p>
    </div>
  )
}
