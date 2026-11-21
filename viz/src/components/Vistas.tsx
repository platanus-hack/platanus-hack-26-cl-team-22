import { useEffect, useRef, useState } from 'react'
import { PAPELES_POLITICA } from '../lib/capas'
import type { Punto } from '../lib/data'
import { SIN_CAMBIO, veredictoComuna } from '../lib/estado'
import { fmt, fmtBanda, fmtPct, fmtSigned } from '../lib/format'
import { TECLAS_POLITICA, textoBanda, veredicto, type ResumenDif } from '../lib/interaccion'
import type { Lena } from '../lib/lena'
import { cruceBanda, DIF_SIN_CAMBIO, nivel, papelNivel, textoNivel } from '../lib/niveles'
import type { ResumenOrigen } from '../lib/origen'
import type { Ranking } from '../lib/scoring'
import type { Aporte, Banda, Comuna, Escenario, Politica, TipoHogar, Validacion, Variable } from '../lib/types'
import { GraficoBanda } from './GraficoBanda'
import { Cifras, ClaveGrafico, Rodela, Sello, type Cifra } from './Papel'
import { TiraPolitica } from './TiraPolitica'

const plural = (n: number, uno: string, varios: string) => `${fmt(n, 0)} ${n === 1 ? uno : varios}`

function fmtPersonas(n: number): string {
  return n >= 1e6 ? `${fmt(n / 1e6, 2)}` : fmt(n, 0)
}
/** "6,49 millones (5,79–6,57 millones)": personas con su banda. */
export function fmtPersonasBanda(p50: number, p10: number, p90: number): string {
  const mill = Math.max(p10, p50, p90) >= 1e6
  const u = mill ? ' millones' : ' personas'
  if (fmtPersonas(p10) === fmtPersonas(p90)) return `${fmtPersonas(p50)}${u}, sin variación entre réplicas`
  return `${fmtPersonas(p50)}${u} (${fmtPersonas(p10)}–${fmtPersonas(p90)}${u})`
}

/* ---------- 1. La cuenca ---------- */

interface CuencaProps {
  comuna: Comuna | undefined
  punto: Punto | undefined
  cortes: readonly number[]
  variable: Variable
  anio: number
  ultimoAnio: number
  escenario: Escenario
  replicas?: number
  origen: ResumenOrigen | null
  nombre: (codigo: string) => string
  aportes: Aporte[]
  politicas: Politica[]
  activas: ReadonlySet<string>
  /** proyección completa de la comuna, para el gráfico cuando no hay origen del aire */
  grafico: {
    anios: number[]
    idxAnio: number
    serie: Banda
    comparacion?: { nombre: string; p50: number[] }
    referencia?: { valor: number; texto: string }
  } | null
}

export function VistaCuenca(p: CuencaProps) {
  if (!p.comuna) return <p className="v-vacia">Elige una comuna en el mapa para ver su proyección.</p>
  const u = p.variable.unidad
  const n = p.punto ? nivel(p.punto.p50, p.cortes) : null
  const cruce = p.punto ? cruceBanda(p.punto, p.cortes) : null
  const ordenados = [...p.aportes].filter((a) => Math.abs(a.delta_p50_final) > 0).sort((a, b) => Math.abs(b.delta_p50_final) - Math.abs(a.delta_p50_final))
  const maxAp = Math.max(0.01, ...ordenados.map((a) => Math.abs(a.delta_p50_final)))
  const veredicto =
    p.punto && p.grafico?.referencia && p.variable.mejor === 'menor'
      ? veredictoComuna(p.grafico.serie.p50, p.grafico.anios, p.grafico.idxAnio, p.grafico.referencia.valor, p.punto)
      : null
  return (
    <div className="v-cuenca">
      <h2 className="v-titulo">{p.comuna.nombre}</h2>
      <div className="cuenca-fila">
        <Rodela
          nivel={n === null ? null : papelNivel(n, p.cortes)}
          borde={cruce ? papelNivel(cruce.nivel, p.cortes) : null}
          etiqueta={p.punto ? `${fmtBanda(p.punto.p50, p.punto.p10, p.punto.p90, u)} en ${p.anio}` : 'Sin dato'}
        >
          <span className="numeral">{p.punto ? fmt(p.punto.p50, 1) : '—'}</span>
        </Rodela>
        <div className="cuenca-lectura">
          {p.punto ? (
            <>
              <p className="banda-grande">
                {fmt(p.punto.p10, 1)}–{fmt(p.punto.p90, 1)} {u}
              </p>
              {veredicto ? (
                <Sello v={veredicto} />
              ) : (
                <p className="chips">
                  <span className={`chip nivel-${papelNivel(n ?? 0, p.cortes)}`}>
                    Nivel {(n ?? 0) + 1} de {p.cortes.length + 1}
                  </span>
                  {cruce && <span className="chip">puede llegar a {textoNivel(cruce.nivel, p.cortes)}</span>}
                </p>
              )}
              <p className="nota">
                Mediana y banda p10–p90, {p.anio}
                {p.replicas ? ` · ${fmt(p.replicas, 0)} réplicas` : ''}
                {veredicto && p.grafico?.referencia ? ` · riesgo: sobre la norma anual de ${fmt(p.grafico.referencia.valor, 0)} ${u}` : ''}
              </p>
            </>
          ) : (
            <p>Esta comuna no tiene dato en el archivo de simulación.</p>
          )}
        </div>
      </div>

      {p.origen && (
        <section className="bloque" aria-labelledby="h-origen">
          <h3 id="h-origen">De dónde viene su aire</h3>
          <ul className="barras">
            {p.origen.propia !== null && (
              <li>
                <span className="barra-txt">Sus propias emisiones</span>
                <span className="barra-pista">
                  <span className={`barra ${n === null ? 'nivel-0' : `nivel-${papelNivel(n, p.cortes)}`}`} style={{ width: `${p.origen.propia * 100}%` }} />
                </span>
                <span className="barra-num">{fmtPct(p.origen.propia)}</span>
              </li>
            )}
            {p.origen.otros.slice(0, 4).map((o) => (
              <li key={o.origen}>
                <span className="barra-txt">{p.nombre(o.origen)}</span>
                <span className="barra-pista">
                  <span className="barra barra-tinta" style={{ width: `${o.fraccion * 100}%` }} />
                </span>
                <span className="barra-num">{fmtPct(o.fraccion)}</span>
              </li>
            ))}
            <li>
              <span className="barra-txt">Otras comunas y fondo regional</span>
              <span className="barra-pista">
                <span
                  className="barra barra-resto"
                  style={{ width: `${(p.origen.resto + p.origen.otros.slice(4).reduce((s, o) => s + o.fraccion, 0)) * 100}%` }}
                />
              </span>
              <span className="barra-num">{fmtPct(p.origen.resto + p.origen.otros.slice(4).reduce((s, o) => s + o.fraccion, 0))}</span>
            </li>
          </ul>
        </section>
      )}

      {!p.origen && p.grafico && (
        <section className="bloque cuenca-grafico" aria-label={`Proyección de ${p.comuna.nombre}`}>
          <ClaveGrafico nivelBanda={n} comparacion={p.grafico.comparacion?.nombre} />
          <GraficoBanda
            anios={p.grafico.anios}
            serie={p.grafico.serie}
            comparacion={p.grafico.comparacion}
            idxAnio={p.grafico.idxAnio}
            unidad={u}
            referencia={p.grafico.referencia}
            nivelBanda={n}
            alto={128}
          />
        </section>
      )}

      {!p.origen && ordenados.length > 0 && (
        <section className="bloque" aria-labelledby="h-aportes">
          <h3 id="h-aportes">Lo que mueve cada plan aquí</h3>
          <ul className="barras">
            {ordenados.map((a) => {
              const i = p.politicas.findIndex((x) => x.id === a.politica_id)
              const pol = p.politicas[i]
              return (
                <li key={a.politica_id}>
                  <span className="barra-txt">{pol?.nombre ?? a.politica_id}</span>
                  <span className="barra-pista">
                    <span
                      className={`barra pol-${Math.max(0, i) % PAPELES_POLITICA}`}
                      style={{ width: `${(Math.abs(a.delta_p50_final) / maxAp) * 100}%` }}
                    />
                  </span>
                  <span className="barra-num">
                    {fmtSigned(a.delta_p50_final)} {u}
                  </span>
                </li>
              )
            })}
          </ul>
          <p className="nota">Cambio de la mediana a {p.ultimoAnio}, por política.</p>
        </section>
      )}
    </div>
  )
}

/* ---------- 2. El plan ---------- */

interface PlanProps {
  politicas: Politica[]
  comunas: Comuna[]
  activas: ReadonlySet<string>
  escenario: Escenario
  base: Escenario | undefined
  calculada: boolean
  significadoSin?: string
  lecturas: { id: string; texto: string }[]
  lectura: string | undefined
  onLectura: (id: string) => void
  onAlternar: (id: string) => void
  puedeDiferencia: boolean
  resumen: ResumenDif | null
  variable: Variable
  anio: number
  nombre: (codigo: string) => string
  impacto: { metrica: string; norma?: number; actual?: Banda; base?: Banda; idx: number } | null
}

export function VistaPlan(p: PlanProps) {
  const u = p.variable.unidad
  const imp = p.impacto
  const ia = imp?.actual
  const ib = imp?.base
  const i = imp?.idx ?? 0
  return (
    <div className="v-plan">
      {imp && ia && ia.p50[i] !== undefined && (() => {
        const p50 = ia.p50[i]!
        const esc = Math.max(p50, ia.p90[i]!) >= 1e6 ? { d: 1e6, u: 'millones' } : { d: 1e3, u: 'mil' }
        const banda = textoBanda(ia.p10[i]! / esc.d, ia.p90[i]! / esc.d, (n) => fmt(n, 2), esc.u)
        return (
          <div className="cuenca-fila plan-fila">
            <Rodela nivel={4} borde={null} etiqueta={`${fmt(p50 / esc.d, 2)} ${esc.u} de personas sobre la norma en ${p.anio}, banda ${banda}`}>
              <span className="numeral">
                {fmt(p50 / esc.d, 1)}
                <small> {esc.u}</small>
              </span>
            </Rodela>
            <div className="cuenca-lectura">
              <p className="banda-grande">{banda}</p>
              <p>
                {imp.metrica}
                {imp.norma !== undefined ? ` (${fmt(imp.norma, 0)} ${u})` : ''}, {p.anio}.
              </p>
              {ib && ib !== ia && ib.p50[i] !== undefined && p.base && (
                <p>
                  Con «{p.base.nombre}»: {fmtPersonasBanda(ib.p50[i]!, ib.p10[i]!, ib.p90[i]!)}.
                </p>
              )}
            </div>
          </div>
        )
      })()}
      <div className="tiras">
        {p.politicas.map((pol, idx) => (
          <TiraPolitica
            key={pol.id}
            politica={pol}
            indice={idx}
            tecla={TECLAS_POLITICA[idx]}
            pegada={p.activas.has(pol.id)}
            comunas={p.comunas}
            onAlternar={() => p.onAlternar(pol.id)}
          />
        ))}
      </div>
      {p.significadoSin && <p className="nota nota-sin">{p.significadoSin}</p>}
      {p.lecturas.length > 1 && (
        <div className="lecturas" role="radiogroup" aria-label="Lectura de la credibilidad">
          <div className="lecturas-fila">
            {p.lecturas.map((l) => (
              <button key={l.id} type="button" role="radio" aria-checked={p.lectura === l.id} className="lectura" title={l.texto} onClick={() => p.onLectura(l.id)}>
                {l.id.charAt(0).toUpperCase() + l.id.slice(1).replace(/-/g, ' ')}
              </button>
            ))}
          </div>
          {/* Con el plan intacto se lee qué significa la lectura; tras un cambio, el espacio es para el resultado */}
          {!p.puedeDiferencia && p.calculada && <p className="nota">{p.lecturas.find((l) => l.id === p.lectura)?.texto}</p>}
        </div>
      )}
      {!p.calculada && (
        <p className="aviso" role="status">
          Esta combinación no está calculada. El mapa sigue mostrando «{p.escenario.nombre}».
        </p>
      )}
      {p.calculada && p.resumen && p.base && p.puedeDiferencia && (
        <p className="resumen">
          Frente a «{p.base.nombre}», en {p.anio}: {plural(p.resumen.mejoran, 'comuna mejora', 'comunas mejoran')}, {fmt(p.resumen.empeoran, 0)} empeoran y{' '}
          {fmt(p.resumen.sinCambio, 0)} no cambian (menos de {fmt(DIF_SIN_CAMBIO, 1)} {u}).
          {p.resumen.mayor &&
            ` Mayor cambio, ${p.nombre(p.resumen.mayor.codigo)}: ${fmtBanda(p.resumen.mayor.dif.activo.p50, p.resumen.mayor.dif.activo.p10, p.resumen.mayor.dif.activo.p90, '')} contra ${fmtBanda(p.resumen.mayor.dif.base.p50, p.resumen.mayor.dif.base.p10, p.resumen.mayor.dif.base.p90, u)}.`}
        </p>
      )}
    </div>
  )
}

/* ---------- 3. La leña ---------- */

export function VistaLena({ lena }: { lena: Lena | null }) {
  if (!lena)
    return (
      <div className="v-lena">
        <p className="v-vacia">
          Falta el archivo datos/lena.json. Genéralo con <span className="cmd">python -I datos/viz/build_lena.py</span> y vuelve a cargar la página.
        </p>
      </div>
    )
  const a = lena.zonas.A
  const b = lena.zonas.B
  const sinDato = [...a.sinDato, ...b.sinDato]
  return (
    <div className="v-lena">
      <p className="etiqueta-real">Datos reales: RETC {lena.anio || 2023} y D.S. 31/2016</p>
      <div className="cuenca-fila">
        <Rodela nivel={3} borde={null} etiqueta={`${fmtPct(b.parteEmisiones)} de las emisiones de leña está en la Zona B`}>
          <span className="numeral numeral-pct">
            {fmt(b.parteEmisiones * 100, 0)}
            <small> %</small>
          </span>
        </Rodela>
        <p className="lena-frase">
          De las emisiones de MP2,5 por leña de la región, el {fmtPct(b.parteEmisiones)} sale de la Zona B, donde vive el {fmtPct(b.partePoblacion)} de la gente. El
          plan prohíbe calefactores a leña solo en la Zona A (art. 74); en la Zona B solo restringe los nuevos (art. 75).
        </p>
      </div>
      <section className="bloque" aria-label="Las dos zonas comparadas">
        {[
          { t: 'Emisiones de leña', a: a.parteEmisiones, b: b.parteEmisiones, ta: `${fmt(a.toneladas, 0)} t`, tb: `${fmt(b.toneladas, 0)} t` },
          { t: 'Población', a: a.partePoblacion, b: b.partePoblacion, ta: `${fmt(a.poblacion / 1e6, 2)} millones`, tb: `${fmt(b.poblacion / 1e6, 2)} millones` },
        ].map((f) => (
          <div className="apilada" key={f.t}>
            <span className="apilada-titulo">{f.t}</span>
            <div className="apilada-barra" role="img" aria-label={`${f.t}: Zona A ${fmtPct(f.a)}, Zona B ${fmtPct(f.b)}`}>
              <span className="apilada-a zona-a" style={{ flexBasis: `${f.a * 100}%` }}>
                {f.a >= 0.14 && `A ${fmtPct(f.a)}`}
              </span>
              <span className="apilada-b zona-b" style={{ flexBasis: `${f.b * 100}%` }}>
                {f.b >= 0.14 && `B ${fmtPct(f.b)}`}
              </span>
            </div>
            <span className="apilada-pie">
              Zona A: {fmtPct(f.a)} ({f.ta}) · Zona B: {fmtPct(f.b)} ({f.tb})
            </span>
          </div>
        ))}
      </section>
      <p className="nota">
        Zona A: {a.comunas} comunas (provincia de Santiago, San Bernardo y Puente Alto). Zona B: las otras {b.comunas}.
        {sinDato.length > 0 && ` Sin dato de leña en el RETC: ${sinDato.join(', ')}.`} Esta hoja no cambia con el año ni con los planes.
      </p>
    </div>
  )
}

/* ---------- 4. Mi comuna ---------- */

interface ComunaProps {
  tipos: TipoHogar[]
  perfilId: string
  pesos: Record<string, number>
  claves: string[]
  conDato: ReadonlySet<string>
  nombreVariable: (id: string) => string
  onPerfil: (id: string) => void
  onPeso: (id: string, v: number) => void
  ranking: Ranking
  nombre: (codigo: string) => string
  seleccionada: string | null
  onSeleccionar: (codigo: string) => void
  detalle: {
    comuna: Comuna
    serie: Banda
    comparacion?: { nombre: string; p50: number[] }
    hallazgos: string[]
    nivelBanda: number | null
  } | null
  anios: number[]
  idxAnio: number
  variable: Variable
  referencia?: { valor: number; texto: string }
  puntos: ReadonlyMap<string, Punto>
  cortes: readonly number[]
  aportes: Aporte[]
  politicas: Politica[]
}

export const PERSONALIZADO = '__personalizado'

export function VistaComuna(p: ComunaProps) {
  const { ignoradas } = p.ranking
  const [ajustar, setAjustar] = useState(false)
  const lista = useRef<HTMLOListElement>(null)
  const u = p.variable.unidad
  const anio = p.anios[p.idxAnio]
  const puesto = p.ranking.filas.findIndex((f) => f.codigo === p.seleccionada) + 1

  // La comuna elegida (también desde el mapa) queda a la vista en la lista.
  useEffect(() => {
    lista.current?.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [p.seleccionada, p.ranking])

  const veredicto =
    p.detalle && p.referencia && p.variable.mejor === 'menor'
      ? veredictoComuna(p.detalle.serie.p50, p.anios, p.idxAnio, p.referencia.valor, {
          p10: p.detalle.serie.p10[p.idxAnio] ?? NaN,
          p90: p.detalle.serie.p90[p.idxAnio] ?? NaN,
        })
      : null
  const cifras: Cifra[] = []
  let top: { nombre: string; indice: number; delta: number } | null = null
  if (p.detalle) {
    const s = p.detalle.serie
    const n = p.anios.length
    const v = s.p50[p.idxAnio]
    if (v !== undefined) {
      cifras.push({ etiqueta: `En ${anio}`, valor: fmt(v, 1), nota: `banda ${fmt(s.p10[p.idxAnio]!, 1)}–${fmt(s.p90[p.idxAnio]!, 1)}` })
      if (p.referencia)
        cifras.push({ etiqueta: `Norma ${fmt(p.referencia.valor, 0)}`, valor: fmtSigned(v - p.referencia.valor), nota: v > p.referencia.valor ? 'sobre la norma' : 'bajo la norma' })
    }
    if (n >= 2 && s.p50[0] !== undefined && s.p50[n - 1] !== undefined) {
      const d = s.p50[n - 1]! - s.p50[0]!
      const mejora = p.variable.mejor === 'menor' ? d < 0 : d > 0
      const quieto = Math.abs(d) <= SIN_CAMBIO
      cifras.push({
        etiqueta: `${p.anios[0]} → ${p.anios[n - 1]}`,
        valor: fmtSigned(d),
        nota: quieto ? 'sin cambio' : mejora ? 'mejora' : 'empeora',
        tono: quieto ? undefined : mejora ? 'mejora' : 'empeora',
      })
    }
    const a = [...p.aportes].sort((x, y) => Math.abs(y.delta_p50_final) - Math.abs(x.delta_p50_final))[0]
    if (a && Math.abs(a.delta_p50_final) > 0) {
      const i = p.politicas.findIndex((x) => x.id === a.politica_id)
      top = { nombre: p.politicas[i]?.nombre ?? a.politica_id, indice: Math.max(0, i), delta: a.delta_p50_final }
    }
  }

  return (
    <div className="v-comuna">
      <section className="paso" aria-labelledby="h-prioridad">
        <div className="paso-cabeza">
          <h3 id="h-prioridad">Qué te importa</h3>
          <button type="button" className="lectura ajustar" aria-expanded={ajustar} aria-controls="pesos" onClick={() => setAjustar((x) => !x)}>
            {ajustar ? 'Ocultar pesos' : 'Ajustar pesos'}
          </button>
        </div>
        <div className="perfiles" role="radiogroup" aria-label="Perfil del hogar">
          {p.tipos.map((t) => (
            <button key={t.id} type="button" role="radio" aria-checked={p.perfilId === t.id} className="lectura" onClick={() => p.onPerfil(t.id)}>
              {t.nombre}
            </button>
          ))}
        </div>
        {ajustar && (
          <div className="pesos" id="pesos">
            {p.claves.map((k) => {
              const hay = p.conDato.has(k)
              return (
                <label className={`peso${hay ? '' : ' sin-dato'}`} key={k}>
                  <span className="peso-nombre">{p.nombreVariable(k)}</span>
                  <input type="range" min={0} max={1} step={0.05} value={p.pesos[k] ?? 0} disabled={!hay} onChange={(e) => p.onPeso(k, Number(e.target.value))} />
                  <span className="peso-num">{hay ? fmt(p.pesos[k] ?? 0, 2) : 'sin dato'}</span>
                </label>
              )
            })}
          </div>
        )}
        {ignoradas.length > 0 && <p className="nota">Sin datos para {ignoradas.map(p.nombreVariable).join(', ')}: no cuenta en el orden.</p>}
      </section>

      <section className="paso" aria-labelledby="h-ranking">
        <h3 id="h-ranking">
          Mejores comunas para ti
          <span className="grafico-clave">
            puntaje · PM2,5 {anio}
          </span>
        </h3>
        <ol className="ranking" ref={lista}>
          {p.ranking.filas.map((f, i) => {
            const pt = p.puntos.get(f.codigo)
            return (
              <li key={f.codigo}>
                <button type="button" className="ranking-fila" aria-pressed={f.codigo === p.seleccionada} onClick={() => p.onSeleccionar(f.codigo)}>
                  <span className="ranking-pos">{i + 1}</span>
                  <span className="ranking-nombre">{p.nombre(f.codigo)}</span>
                  <span className="ranking-pista">
                    <span className="ranking-barra" style={{ width: `${f.puntaje ?? 0}%` }} />
                  </span>
                  <span className="ranking-num">{f.puntaje === null ? '—' : fmt(f.puntaje, 0)}</span>
                  <span className="ranking-valor">
                    {pt && <i className={`tag-muestra nivel-${papelNivel(nivel(pt.p50, p.cortes), p.cortes)}`} />}
                    {pt ? fmt(pt.p50, 1) : '—'}
                  </span>
                </button>
              </li>
            )
          })}
        </ol>
      </section>

      {p.detalle && (
        <section className="paso detalle" aria-labelledby="h-detalle">
          <h3 id="h-detalle">
            {p.detalle.comuna.nombre}
            {puesto > 0 && (
              <span className="grafico-clave">
                puesto {puesto} de {p.ranking.filas.length} · {u}
              </span>
            )}
          </h3>
          {veredicto && <Sello v={veredicto} />}
          <Cifras items={cifras} />
          <ClaveGrafico nivelBanda={p.detalle.nivelBanda} comparacion={p.detalle.comparacion?.nombre} />
          <GraficoBanda
            anios={p.anios}
            serie={p.detalle.serie}
            comparacion={p.detalle.comparacion}
            idxAnio={p.idxAnio}
            unidad={u}
            referencia={p.referencia}
            nivelBanda={p.detalle.nivelBanda}
            alto={104}
          />
          {top && (
            <p className="clave-politica">
              <i className={`tag-muestra pol-${top.indice % PAPELES_POLITICA}`} />
              <span>Lo que más la mueve: {top.nombre}</span>
              <b>
                {fmtSigned(top.delta)} {u}
              </b>
            </p>
          )}
        </section>
      )}
    </div>
  )
}

/* ---------- 5. La prueba ---------- */

const TITULOS: Record<string, string> = {
  cambio_2017_2023: 'Cambio de 2017 a 2023',
  niveles_2024: 'Niveles de 2024',
  ajuste_2023: 'Ajuste con 2023',
}
const NOMBRES: Record<string, string> = {
  rmse_modelo: 'Modelo',
  rmse_sin_cambio: 'Suponer que nada cambia',
  rmse_mismo_cambio_en_todas: 'El mismo cambio en todas',
  rmse_persistencia: 'Repetir el año anterior',
  rmse_media_otras_estaciones: 'Media de las otras estaciones',
}
const humano = (s: string) => {
  const t = s.replace(/_/g, ' ').replace(/(\d{4}) (\d{4})/, '$1 a $2')
  return t.charAt(0).toUpperCase() + t.slice(1)
}

export function VistaPrueba({ validacion, aviso, unidad }: { validacion: Validacion; aviso?: string; unidad: string }) {
  return (
    <div className="v-prueba">
      <p className="v-escenario">
        El modelo contra mediciones reales de las estaciones, en años que no usó para ajustarse. El error es la raíz del error cuadrático medio entre
        estaciones: menor es mejor.
      </p>
      {validacion.bloques.map((b) => {
        const errores = b.valores.filter((v) => v.clave.startsWith('rmse_'))
        const otros = b.valores.filter((v) => !v.clave.startsWith('rmse_'))
        const max = Math.max(0.01, ...errores.map((e) => e.valor))
        const modelo = errores.find((e) => e.clave === 'rmse_modelo')
        const rivales = errores.filter((e) => e !== modelo)
        const mejorRival = rivales.length > 0 ? rivales.reduce((m, e) => (e.valor < m.valor ? e : m)) : null
        const obs = otros.find((v) => v.clave === 'observado_media')
        const mod = otros.find((v) => v.clave === 'modelo_media')
        const resto = otros.filter((v) => v !== obs && v !== mod)
        return (
          <section className="bloque prueba" key={b.id} aria-labelledby={`h-${b.id}`}>
            <h3 id={`h-${b.id}`}>{TITULOS[b.id] ?? humano(b.id)}</h3>
            {obs && mod && (
              <p className="prueba-frase">
                Observado <b>{fmtSigned(obs.valor)} {unidad}</b>, modelo <b>{fmtSigned(mod.valor)} {unidad}</b> en promedio.
              </p>
            )}
            {errores.length > 0 && (
              <>
                <ul className="barras">
                  {errores.map((e) => (
                    <li key={e.clave}>
                      <span className="barra-txt">{NOMBRES[e.clave] ?? humano(e.clave.replace(/^rmse_/, ''))}</span>
                      <span className="barra-pista">
                        <span className={`barra ${e === modelo ? 'barra-tinta' : 'barra-alt'}`} style={{ width: `${(e.valor / max) * 100}%` }} />
                      </span>
                      <span className="barra-num">
                        {fmt(e.valor, 2)} {unidad}
                      </span>
                    </li>
                  ))}
                </ul>
                {modelo && mejorRival && (
                  <p className="prueba-veredicto">
                    {{
                      gana: 'Error por estación: el modelo gana a todas las alternativas simples.',
                      empata: `Error por estación: el modelo empata con «${NOMBRES[mejorRival.clave] ?? humano(mejorRival.clave)}».`,
                      pierde: `Error por estación: el modelo pierde contra «${NOMBRES[mejorRival.clave] ?? humano(mejorRival.clave)}».`,
                    }[veredicto(modelo.valor, mejorRival.valor)]}
                  </p>
                )}
              </>
            )}
            {resto.length > 0 && (
              <p className="prueba-frase">
                {resto.map((v) => `${v.clave === 'r2' ? 'R²' : humano(v.clave)} ${fmt(v.valor, Number.isInteger(v.valor) ? 0 : 2)}`).join(' · ')}
              </p>
            )}
          </section>
        )
      })}
      {aviso && <p className="aviso aviso-honesto">{aviso}</p>}
    </div>
  )
}

