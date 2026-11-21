import { fmt, fmtPct } from '../lib/format'
import { TECLAS_POLITICA, textoBanda, type ResumenDif } from '../lib/interaccion'
import type { Lena } from '../lib/lena'
import { DIF_SIN_CAMBIO } from '../lib/niveles'
import { TOLERANCIA, contarPruebas, resumirPruebas, type FilaPrueba, type Resultado } from '../lib/pruebas'
import type { Banda, Comuna, Escenario, Politica, Validacion, Variable } from '../lib/types'
import { Desplegable } from './Desplegable'
import { Cifras } from './Papel'
import { TiraPolitica } from './TiraPolitica'

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

const tituloLectura = (id: string) => id.charAt(0).toUpperCase() + id.slice(1).replace(/-/g, ' ')

export function VistaPlan(p: PlanProps) {
  const u = p.variable.unidad
  const imp = p.impacto
  const ia = imp?.actual
  const ib = imp?.base
  const i = imp?.idx ?? 0
  const p50 = ia?.p50[i]
  const esc = ia && p50 !== undefined && Math.max(p50, ia.p90[i] ?? 0) >= 1e6 ? { d: 1e6, u: 'millones' } : { d: 1e3, u: 'mil' }
  const antes = ib && ib !== ia ? ib.p50[i] : undefined
  return (
    <div className="v-plan">
      {imp && ia && p50 !== undefined && (
        <div className="plan-cifra">
          <p className="plan-num">
            {fmt(p50 / esc.d, 1)}
            <small> {esc.u}</small>
          </p>
          <div className="plan-que">
            <p>
              <b>de personas viven sobre la norma</b>
              {imp.norma !== undefined ? ` de ${fmt(imp.norma, 0)} ${u}` : ''} · {p.anio}
            </p>
            <p className="nota">
              Banda {textoBanda(ia.p10[i]! / esc.d, ia.p90[i]! / esc.d, (n) => fmt(n, 2), esc.u)}
              {antes !== undefined && p.base ? ` · con «${p.base.nombre}»: ${fmt(antes / esc.d, 2)} ${esc.u}` : ''}
            </p>
          </div>
        </div>
      )}

      <div className="plan-cabeza">
        <h3>Planes</h3>
        {p.lecturas.length > 1 && (
          <Desplegable
            etiqueta="Lo que no tiene evidencia"
            valor={p.lectura}
            onCambiar={p.onLectura}
            opciones={p.lecturas.map((l) => ({ id: l.id, titulo: tituloLectura(l.id), detalle: l.texto }))}
          />
        )}
      </div>
      <p className="plan-columnas" aria-hidden="true">
        <span>Clic o tecla para encender o apagar</span>
        <span>Probabilidad de cumplirse</span>
      </p>
      <div className="plan-lista">
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

      {!p.calculada && (
        <p className="aviso" role="status">
          Esta combinación no está calculada. El mapa sigue mostrando «{p.escenario.nombre}».
        </p>
      )}
      {p.calculada && p.resumen && p.base && p.puedeDiferencia && (
        <section className="plan-efecto" aria-label={`Efecto frente a ${p.base.nombre}`}>
          <h3>
            Frente a «{p.base.nombre}»<span className="grafico-clave">{p.anio}</span>
          </h3>
          <Cifras
            items={[
              { etiqueta: 'Mejoran', valor: fmt(p.resumen.mejoran, 0), nota: 'comunas', tono: p.resumen.mejoran > 0 ? 'mejora' : undefined },
              { etiqueta: 'Empeoran', valor: fmt(p.resumen.empeoran, 0), nota: 'comunas', tono: p.resumen.empeoran > 0 ? 'empeora' : undefined },
              { etiqueta: 'No cambian', valor: fmt(p.resumen.sinCambio, 0), nota: `menos de ${fmt(DIF_SIN_CAMBIO, 1)} ${u}` },
            ]}
          />
          {p.resumen.mayor && (
            <p className="nota">
              Mayor cambio: {p.nombre(p.resumen.mayor.codigo)}, de {fmt(p.resumen.mayor.dif.base.p50, 1)} a {fmt(p.resumen.mayor.dif.activo.p50, 1)} {u}.
            </p>
          )}
        </section>
      )}
      {p.significadoSin && !p.puedeDiferencia && <p className="nota">{p.significadoSin}</p>}
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
  const filas = [
    { t: 'Emisiones de leña', a: a.parteEmisiones, b: b.parteEmisiones },
    { t: 'Población', a: a.partePoblacion, b: b.partePoblacion },
  ]
  return (
    <div className="v-lena">
      <p className="etiqueta-real">Datos reales: RETC {lena.anio || 2023} y D.S. 31/2016</p>
      <h2 className="lena-titular">La prohibición de leña deja fuera el {fmtPct(b.parteEmisiones)} de las emisiones</h2>
      <Cifras
        items={[
          { etiqueta: 'De la leña sale de la Zona B', valor: fmtPct(b.parteEmisiones), nota: `${fmt(b.toneladas, 0)} t de MP2,5 al año`, tono: 'empeora' },
          { etiqueta: 'De la gente vive en la Zona B', valor: fmtPct(b.partePoblacion), nota: `${fmt(b.poblacion / 1e6, 2)} millones de personas` },
        ]}
      />
      <section className="lena-barras" aria-label="Las dos zonas comparadas">
        {filas.map((f) => (
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
          </div>
        ))}
      </section>
      <ul className="lena-zonas">
        <li>
          <i className="tag-muestra zona-a" />
          <b>Zona A</b>
          <span>{a.comunas} comunas · leña prohibida (art. 74)</span>
        </li>
        <li>
          <i className="tag-muestra zona-b" />
          <b>Zona B</b>
          <span>{b.comunas} comunas · solo se restringen los calefactores nuevos (art. 75)</span>
        </li>
      </ul>
      {sinDato.length > 0 && <p className="nota">Sin dato de leña en el RETC: {sinDato.join(', ')}.</p>}
    </div>
  )
}

/* ---------- La prueba ---------- */

const TEXTO_RESULTADO: Record<Resultado, string> = { gana: 'Gana', empata: 'Empata', pierde: 'Pierde' }
const SELLO_RESULTADO: Record<Resultado, string> = { gana: 'cumple', empata: 'limite', pierde: 'riesgo' }

function errorTxt(f: FilaPrueba, v: number, unidad: string): string {
  if (f.formato === 'pct') return `${fmt(v * 100, 1)} %`
  if (f.formato === 'personas') return `${fmt(v, 0)} personas`
  return `${fmt(v, 2)} ${unidad}`
}

export function VistaPrueba({ validacion, aviso, unidad }: { validacion: Validacion; aviso?: string; unidad: string }) {
  const filas = resumirPruebas(validacion)
  const n = contarPruebas(filas)
  return (
    <div className="v-prueba">
      <h2 className="lena-titular">El modelo contra datos que no vio</h2>
      <Cifras
        items={[
          { etiqueta: 'Gana', valor: fmt(n.gana, 0), nota: `de ${filas.length} pruebas`, tono: n.gana > 0 ? 'mejora' : undefined },
          { etiqueta: 'Empata', valor: fmt(n.empata, 0), nota: `por menos de ${fmt((validacion.tolerancia ?? TOLERANCIA) * 100, 0)} %` },
          { etiqueta: 'Pierde', valor: fmt(n.pierde, 0), nota: 'y se publica igual', tono: n.pierde > 0 ? 'empeora' : undefined },
        ]}
      />
      <ul className="marcador">
        {filas.map((f) => (
          <li key={f.id}>
            <span className={`sello sello-${SELLO_RESULTADO[f.resultado]}`}>{TEXTO_RESULTADO[f.resultado]}</span>
            <span className="marcador-txt">
              <b>{f.titulo}</b>
              <small>
                Modelo {errorTxt(f, f.modelo, unidad)} · {f.rival.nombre} {errorTxt(f, f.rival.valor, unidad)}
              </small>
            </span>
          </li>
        ))}
      </ul>
      <p className="nota">
        Error fuera de muestra: menor es mejor. Cada prueba ajusta el modelo con un período y lo compara con otro que no vio; se calcula una vez con
        datos del pasado, así que no cambia con la comuna, el escenario ni tus prioridades.
      </p>
      {aviso && (
        <details className="limites">
          <summary>Qué no sabe el modelo</summary>
          <p>{aviso}</p>
        </details>
      )}
    </div>
  )
}
