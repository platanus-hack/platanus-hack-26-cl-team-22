import { LARGO_CAMBIO, rangosDe } from '../lib/onboarding'
import { Desplegable } from './Desplegable'
import { useEffect, useRef, useState } from 'react'
import { PAPELES_POLITICA } from '../lib/capas'
import type { Punto } from '../lib/data'
import type { Estado, Veredicto } from '../lib/estado'
import { fmt, fmtSigned } from '../lib/format'
import { nivel, papelNivel } from '../lib/niveles'
import { CORTES_RIESGO, decimales, ESTADO_DE_RIESGO, nivelRiesgo, TEXTO_RIESGO, veredictoGeneral, type Riesgo } from '../lib/riesgo'
import type { Aporte, Banda, Comuna, Politica, TipoHogar } from '../lib/types'
import { ordenarPorPeso, type VariableCorta } from '../lib/variables'
import { GraficoBanda } from './GraficoBanda'
import { ClaveGrafico, Rodela, Sello } from './Papel'

export const GENERAL = 'general'
export const PERSONALIZADO = '__personalizado'

const papelRiesgo = (r: number) => papelNivel(nivel(r, CORTES_RIESGO), CORTES_RIESGO)
const valorTxt = (v: number | undefined, unidad: string) => (v === undefined ? 'sin dato' : `${fmt(v, decimales(v))}${unidad === '%' ? ' %' : ''}`)

interface Props {
  /** todas las variables del índice: las simuladas y los indicadores de inversión */
  variables: VariableCorta[]
  /** ids de los indicadores de inversión: entran al índice, pero no tienen serie ni capa de detalle */
  extras: ReadonlySet<string>
  /** rango aceptado por variable (id de la opción) */
  rangos: Record<string, string>
  onRango: (variable: string, id: string) => void
  /** resultado de la entrada guiada: para quién es el orden y por qué */
  guia?: {
    titulo: string
    texto: string
    cargando: boolean
    porIA: boolean
    onCambiar: () => void
    /** cambia el requerimiento con una frase («ahora me importa más la seguridad») y reordena */
    onModificar?: (texto: string) => void
    /** el caso depende del agua y hay caudales medidos: lleva a verlos */
    onAgua?: () => void
    /** Claude está leyendo el caso */
    leyendo?: boolean
    /** ajustes de prioridad que Claude propuso a partir del caso; la persona puede apagarlos */
    ajustes?: { variable: string; texto: string; cita: string; activo: boolean }[]
    notas?: string[]
    onAlternarAjuste?: (variable: string) => void
  } | null
  capa: string
  onCapa: (id: string) => void

  tipos: TipoHogar[]
  perfilId: string
  /** prioridad de cada variable, de 0 a 10 */
  pesos: Record<string, number>
  onPerfil: (id: string) => void
  onPeso: (id: string, v: number) => void

  riesgo: Riesgo
  /** el mismo índice en el último año, para decir hacia dónde va */
  riesgoFin: Riesgo
  anio: number
  ultimoAnio: number
  nombre: (codigo: string) => string
  comuna: Comuna | undefined
  onSeleccionar: (codigo: string) => void
  /** mediana de cada variable en la comuna elegida, en el año elegido */
  valores: Record<string, number | undefined>
  /** sello propio de una variable (p. ej. la norma del aire) que reemplaza al de posición */
  sellos: Record<string, { estado: Estado; texto: string } | undefined>
  /** comunas que cumplen todos los rangos aceptados; null si no hay rangos */
  dentro: ReadonlySet<string> | null
  /** variables en que la comuna elegida queda fuera de rango */
  fuera: string[]

  /** detalle de la variable de la capa, si la capa no es la general */
  detalle: {
    variable: VariableCorta
    punto: Punto | undefined
    serie: Banda
    comparacion?: { nombre: string; p50: number[] }
    referencia?: { valor: number; texto: string }
    veredicto: Veredicto | null
    /** papel (0 a 5) del valor en la rodela */
    papel: number | null
    aportes: Aporte[]
  } | null
  anios: number[]
  idxAnio: number
  politicas: Politica[]
}

/** Una línea para cambiar el requerimiento en lenguaje natural, sin volver a la entrada. */
function Modificar({ onEnviar, ocupado }: { onEnviar: (texto: string) => void; ocupado: boolean }) {
  const [texto, setTexto] = useState('')
  const listo = texto.trim().length >= 3 && !ocupado
  return (
    <form
      className="guia-modificar"
      onSubmit={(e) => {
        e.preventDefault()
        if (!listo) return
        onEnviar(texto.trim())
        setTexto('')
      }}
    >
      <label htmlFor="guia-modificar">Cambia tu requerimiento</label>
      <div className="guia-modificar-fila">
        <input
          id="guia-modificar"
          type="text"
          value={texto}
          maxLength={LARGO_CAMBIO}
          autoComplete="off"
          placeholder="Cambia tu requerimiento: «ahora me importa más la seguridad que el aire»"
          onChange={(e) => setTexto(e.target.value)}
        />
        <button type="submit" className="lectura" disabled={!listo}>
          Actualizar
        </button>
      </div>
    </form>
  )
}

export function VistaRiesgo(p: Props) {
  const general = p.capa === GENERAL
  return (
    <div className="v-riesgo">
      {general ? <General {...p} /> : <Detalle {...p} />}
    </div>
  )
}

/* ---------- Una dimensión: el índice general ---------- */

function General(p: Props) {
  const [ajustar, setAjustar] = useState(false)
  const [todas, setTodas] = useState(false)
  const lista = useRef<HTMLOListElement>(null)
  const sel = p.comuna ? p.riesgo.porCodigo.get(p.comuna.codigo) : undefined
  const fin = p.comuna ? p.riesgoFin.porCodigo.get(p.comuna.codigo) : undefined
  const veredicto = sel ? veredictoGeneral(sel, p.riesgo.total, p.anio !== p.ultimoAnio && fin ? { indice: fin.indice, anio: p.ultimoAnio } : undefined) : null
  const conIndice = p.riesgo.filas.filter((f) => f.indice !== null)
  const enRango = p.dentro ? conIndice.filter((f) => p.dentro!.has(f.codigo)) : conIndice
  const filas = todas ? conIndice : enRango.slice(0, 3)

  useEffect(() => {
    if (todas) lista.current?.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [todas, p.comuna?.codigo])

  return (
    <>
      <section className="tramo" aria-labelledby="h-prio">
        <div className="tramo-cabeza">
          <h3 id="h-prio">{p.guia ? p.guia.titulo : 'Qué priorizas'}</h3>
          <div className="tramo-acciones">
            {p.guia && !ajustar && (
              <button type="button" className="lectura ajustar" onClick={p.guia.onCambiar}>
                Cambiar búsqueda
              </button>
            )}
            <button type="button" className="lectura ajustar" aria-expanded={ajustar} aria-controls="pesos" onClick={() => setAjustar((x) => !x)}>
              {ajustar ? 'Listo' : 'Ajustar pesos'}
            </button>
          </div>
        </div>
        {ajustar ? (
          <div className="pesos" id="pesos">
            <p className="pesos-ayuda">Peso: 0 no cuenta y 10 es lo más importante. «Acepto» deja fuera de las 3 mejores a las comunas que no cumplen ese límite.</p>
            {ordenarPorPeso(p.variables, p.pesos).map((v) => (
              <div className="peso-fila" key={v.id}>
                <label className="peso">
                  <span className="peso-nombre">{v.nombre}</span>
                  <input type="range" min={0} max={10} step={1} value={p.pesos[v.id] ?? 0} onChange={(e) => p.onPeso(v.id, Number(e.target.value))} />
                  <span className="peso-num">{fmt(p.pesos[v.id] ?? 0, 0)}</span>
                </label>
                {rangosDe(v.id).length > 1 && (
                  <Desplegable
                    etiqueta="Acepto"
                    valor={p.rangos[v.id] ?? 'libre'}
                    onCambiar={(id) => p.onRango(v.id, id)}
                    opciones={rangosDe(v.id).map((o) => ({ id: o.id, titulo: o.titulo, detalle: o.detalle }))}
                  />
                )}
              </div>
            ))}
          </div>
        ) : p.guia ? (
          <div className="guia" aria-live="polite">
            <p className={p.guia.cargando ? 'guia-texto guia-cargando' : 'guia-texto'} key={p.guia.texto}>
              {p.guia.texto}
            </p>
            {p.guia.ajustes && p.guia.ajustes.length > 0 && (
              <div className="guia-ajustes" aria-label="Ajustes por lo que contaste">
                <p className="guia-pie">Por lo que contaste:</p>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                  {p.guia.ajustes.map((a) => (
                    <li key={a.variable}>
                      <button
                        type="button"
                        className="pestana-mapa"
                        aria-pressed={a.activo}
                        title={`Porque escribiste: «${a.cita}». Apágalo si no aplica.`}
                        onClick={() => p.guia?.onAlternarAjuste?.(a.variable)}
                      >
                        {a.texto}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {p.guia.notas && p.guia.notas.length > 0 && <p className="guia-pie">{p.guia.notas.join(' ')}</p>}
            {p.guia.porIA && <p className="guia-pie">Redactado por Claude con los números del modelo</p>}
            {p.guia.onAgua && (
              <button type="button" className="lectura ajustar ajustar-agua" onClick={p.guia.onAgua}>
                Ver caudales de los ríos
              </button>
            )}
            {p.guia.onModificar && <Modificar onEnviar={p.guia.onModificar} ocupado={!!p.guia.cargando} />}
          </div>
        ) : (
          <div className="perfiles" role="radiogroup" aria-label="Perfil de prioridades">
            {p.tipos.map((t) => (
              <button key={t.id} type="button" role="radio" aria-checked={p.perfilId === t.id} className="lectura" onClick={() => p.onPerfil(t.id)}>
                {t.nombre}
              </button>
            ))}
            {p.perfilId === PERSONALIZADO && (
              <span className="lectura lectura-fija" aria-current="true">
                A tu medida
              </span>
            )}
          </div>
        )}
      </section>

      <section className="tramo" aria-labelledby="h-top">
        <div className="tramo-cabeza">
          <h3 id="h-top">
            {todas ? 'De menor a mayor riesgo' : 'Las 3 de menor riesgo'}
            <span className="grafico-clave">
              {p.dentro && !todas ? `${enRango.length} de ${conIndice.length} cumplen tus rangos · ` : ''}
              {p.anio}
            </span>
          </h3>
          <button type="button" className="lectura ajustar" aria-expanded={todas} onClick={() => setTodas((x) => !x)}>
            {todas ? 'Solo las 3' : `Ver las ${p.riesgo.total}`}
          </button>
        </div>
        <ol className={`podio${todas ? ' podio-todas' : ''}`} ref={lista}>
          {filas.map((f) => (
            <li key={f.codigo}>
              <button
                type="button"
                className={`podio-fila${p.dentro && !p.dentro.has(f.codigo) ? ' podio-fuera' : ''}`}
                aria-pressed={f.codigo === p.comuna?.codigo}
                onClick={() => p.onSeleccionar(f.codigo)}
              >
                <span className="podio-pos">{f.puesto}</span>
                <span className="podio-nombre">{p.nombre(f.codigo)}</span>
                <span className={`podio-num nivel-${papelRiesgo(f.indice!)} txt-nivel-${papelRiesgo(f.indice!)}`}>{fmt(f.indice!, 0)}</span>
              </button>
            </li>
          ))}
        </ol>
        {!todas && filas.length === 0 && <p className="nota">Ninguna comuna cumple todos tus rangos.</p>}
      </section>

      {p.comuna && sel && sel.indice !== null ? (
        <section className="tramo ficha" aria-labelledby="h-ficha">
          <div className="ficha-cabeza">
            <div className={`indice nivel-${papelRiesgo(sel.indice)} txt-nivel-${papelRiesgo(sel.indice)}`} role="img" aria-label={`Riesgo ${fmt(sel.indice, 0)} de 100`}>
              <b>{fmt(sel.indice, 0)}</b>
              <small>de 100</small>
            </div>
            <div className="ficha-lectura">
              <h2 id="h-ficha">{p.comuna.nombre}</h2>
              {veredicto && <Sello v={veredicto} />}
            </div>
          </div>
          <ul className="dimensiones">
            {/* Solo las variables que pesan en el índice (a lo más tres por perfil), de más a menos peso. */}
            {ordenarPorPeso(p.variables, p.pesos)
              .filter((v) => (p.pesos[v.id] ?? 0) > 0)
              .map((v) => {
                const parte = sel.partes[v.id]
                const extra = p.extras.has(v.id)
                if (parte === undefined)
                  return (
                    <li key={v.id}>
                      <div className="dimension dimension-extra" title={v.que}>
                        <span className="dimension-nombre">{v.nombre}</span>
                        <span className="dimension-pista" aria-hidden="true" />
                        <span className="dimension-valor">—</span>
                        <span className="sello sello-sin">Sin dato</span>
                        <span className="dimension-ir" aria-hidden="true" />
                      </div>
                    </li>
                  )
                const fuera = p.fuera.includes(v.id)
                // El sello dice la posición entre comunas, igual en todas las filas. Lo que diga la norma (solo el
                // aire la tiene) va junto al nombre: una comuna puede estar entre las mejores y aun así sobre la norma.
                const propio = fuera ? { estado: 'riesgo' as const, texto: 'Fuera de tu rango' } : undefined
                const norma = p.sellos[v.id]
                const n = nivelRiesgo(parte)
                const estado = propio?.estado ?? ESTADO_DE_RIESGO[n]
                const contenido = (
                  <>
                    <span className="dimension-nombre">
                      {v.nombre}
                      {norma && <small className={`dimension-norma dimension-norma-${norma.estado}`}>{norma.texto.toLowerCase()}</small>}
                    </span>
                    <span className="dimension-pista" aria-hidden="true">
                      <span className={`dimension-barra sello-${estado}`} style={{ width: `${Math.max(3, parte)}%` }} />
                    </span>
                    <span className="dimension-valor">
                      {valorTxt(p.valores[v.id], v.unidad)}
                      {v.unidad !== '%' && <small> {v.unidad}</small>}
                    </span>
                    <span className={`sello sello-${estado}`}>{propio?.texto ?? TEXTO_RIESGO[n]}</span>
                  </>
                )
                return (
                  <li key={v.id}>
                    {extra ? (
                      // un indicador no tiene serie ni capa propia: se muestra su posición, sin detalle al que ir
                      <div className="dimension dimension-extra" title={v.que}>
                        {contenido}
                        <span className="dimension-ir" aria-hidden="true" />
                      </div>
                    ) : (
                      <button type="button" className="dimension" onClick={() => p.onCapa(v.id)} title={`Ver el detalle de ${v.nombre.toLowerCase()}`}>
                        {contenido}
                        <span className="dimension-ir" aria-hidden="true">
                          ›
                        </span>
                      </button>
                    )}
                  </li>
                )
              })}
          </ul>
          <p className={`nota${todas || ajustar ? ' nota-fuera' : ''}`}>
            Riesgo de 0 a 100: posición entre las {p.riesgo.total} comunas según tus prioridades. 0 es la mejor; 100, la peor.
          </p>
        </section>
      ) : (
        <p className="v-vacia">Elige una comuna en el mapa.</p>
      )}
    </>
  )
}

/* ---------- Una variable en detalle ---------- */

function Detalle(p: Props) {
  const d = p.detalle
  if (!p.comuna) return <p className="v-vacia">Elige una comuna en el mapa.</p>
  if (!d) return <p className="v-vacia">{p.comuna.nombre} no tiene este dato en la simulación.</p>
  const v = d.variable
  const txt = d.punto ? fmt(d.punto.p50, decimales(d.punto.p50)) : '—'
  const aporte = [...d.aportes].sort((a, b) => Math.abs(b.delta_p50_final) - Math.abs(a.delta_p50_final))[0]
  const iPol = aporte ? p.politicas.findIndex((x) => x.id === aporte.politica_id) : -1
  const mejores = [...p.riesgo.filas].filter((f) => f.partes[v.id] !== undefined).sort((a, b) => a.partes[v.id]! - b.partes[v.id]!).slice(0, 3)
  const banda = d.punto && fmt(d.punto.p10, decimales(d.punto.p50)) !== fmt(d.punto.p90, decimales(d.punto.p50))
  return (
    <>
      <div className="cuenca-fila detalle-fila">
        <Rodela nivel={d.papel} borde={null} etiqueta={`${txt} ${v.unidad} en ${p.anio}`}>
          <span className={`numeral${txt.length > 4 ? ' numeral-largo' : ''}`}>{txt}</span>
        </Rodela>
        <div className="cuenca-lectura">
          <h2 className="detalle-nombre">{p.comuna.nombre}</h2>
          <p className="detalle-que">
            {v.que} · {v.unidad}
          </p>
          {d.veredicto && <Sello v={d.veredicto} />}
        </div>
      </div>

      <section className="tramo" aria-label={`Proyección de ${v.nombre.toLowerCase()} en ${p.comuna.nombre}`}>
        <ClaveGrafico nivelBanda={banda ? 0 : null} comparacion={d.comparacion?.nombre} />
        <GraficoBanda anios={p.anios} serie={d.serie} comparacion={d.comparacion} idxAnio={p.idxAnio} unidad={v.unidad} referencia={d.referencia} nivelBanda={0} alto={112} />
      </section>

      {aporte && Math.abs(aporte.delta_p50_final) > 0 && (
        <p className="clave-politica">
          <i className={`tag-muestra pol-${Math.max(0, iPol) % PAPELES_POLITICA}`} />
          <span>Lo que más la mueve: {p.politicas[iPol]?.nombre ?? aporte.politica_id}</span>
          <b>
            {fmtSigned(aporte.delta_p50_final, decimales(aporte.delta_p50_final))}
            {v.unidad === '%' ? ' %' : ''} a {p.ultimoAnio}
          </b>
        </p>
      )}

      <section className="tramo" aria-labelledby="h-mejores">
        <h3 id="h-mejores">
          Las 3 mejores en {v.nombre.toLowerCase()}
          <span className="grafico-clave">{p.anio}</span>
        </h3>
        <div className="perfiles">
          {mejores.map((f) => (
            <button key={f.codigo} type="button" className="lectura" aria-pressed={f.codigo === p.comuna?.codigo} onClick={() => p.onSeleccionar(f.codigo)}>
              {p.nombre(f.codigo)}
            </button>
          ))}
        </div>
      </section>
    </>
  )
}
