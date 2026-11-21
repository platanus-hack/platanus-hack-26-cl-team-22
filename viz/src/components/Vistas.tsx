import { fmt, fmtBanda, fmtPct, fmtSigned } from '../lib/format'
import { TECLAS_POLITICA, textoBanda, veredicto, type ResumenDif } from '../lib/interaccion'
import type { Lena } from '../lib/lena'
import { DIF_SIN_CAMBIO } from '../lib/niveles'
import type { Banda, Comuna, Escenario, Politica, Validacion, Variable } from '../lib/types'
import { Rodela } from './Papel'
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

/* ---------- El plan ---------- */

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

/* ---------- La leña ---------- */

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

/* ---------- La prueba ---------- */

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

