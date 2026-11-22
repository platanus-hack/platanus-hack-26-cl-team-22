import {
  caudalEn,
  CORTE_CRITICO,
  decimalesCaudal,
  estadoCaudal,
  fraccionNormal,
  MESES_CORTOS,
  regimenDe,
  TEXTO_ESTADO,
  variabilidad,
  type Agua,
  type AnioAgua,
  type CauceDato,
  type Estacion,
} from '../lib/agua'
import { ESCENARIOS_AGUA, type EscenarioAgua, type ResumenSim } from '../lib/aguaSim'
import { useState } from 'react'
import { fmt } from '../lib/format'
import { Desplegable } from './Desplegable'
import { IconoJugar } from './Papel'

/** Simulación abierta: el escenario, la década concreta que se reproduce y lo que dicen las 500. */
export interface SimAgua {
  escenario: EscenarioAgua
  /** número de la década mostrada, desde 0 */
  replica: number
  replicas: number
  resumen: ResumenSim
  /** caudal sobre lo normal de la década mostrada, por año */
  decada: number[]
  anios: number[]
  /** año que se mira (el de la línea de tiempo) */
  idx: number
}

interface Props {
  agua: Agua
  estacion: Estacion
  /** el río mapeado: por qué comunas pasa; null si no está en el archivo */
  cauce: CauceDato | null
  onComuna: (codigo: string) => void
  /** qué se mira de lo medido: el promedio (null), la megasequía o un año (índice de `agua.anios`) */
  anio: AnioAgua
  jugando: boolean
  onAnio: (a: AnioAgua) => void
  onJugar: (v: boolean) => void
  onEstacion: (codigo: string) => void
  nombreComuna: (codigo: string | null) => string | null
  /** null = se mira lo medido */
  sim: SimAgua | null
  onSim: (e: EscenarioAgua | null) => void
  onOtraDecada: () => void
  onAnioSim: (i: number) => void
}

const W = 400
const H = 70
const PIE = 14

/**
 * Caudal de un río. Dos lecturas: lo medido (1980–2017) y «¿qué pasaría si…?», que sortea 500 décadas
 * posibles para 2026–2036 según el escenario y reproduce una de ellas en el mapa. La cifra, el sello y las
 * barras toman el color del estado del caudal (normal, bajo o crítico), igual que el río y su punto.
 */
export function VistaAgua(p: Props) {
  const { agua, estacion: e, cauce, anio, sim } = p
  /** el recorrido completo del río, a pedido: por defecto solo el comienzo y el final */
  const [todas, setTodas] = useState(false)
  const anios = agua.anios
  const normal = e.base ?? e.medio
  const fraccion = sim ? (sim.decada[sim.idx] ?? null) : fraccionNormal(e, anio)
  const valor = sim ? (fraccion === null ? null : fraccion * normal) : caudalEn(e, anio)
  const estado = estadoCaudal(fraccion)
  const comuna = p.nombreComuna(e.comuna)
  const opciones = agua.estaciones.map((x) => ({
    id: x.codigo,
    titulo: x.nombre,
    detalle: `${fmt(x.medio, decimalesCaudal(x.medio))} m³/s${x.cambio !== null ? ` · ${fmt(x.cambio, 0)} % en la megasequía` : ''}`,
  }))
  const rango = `${anios[0]}–${anios[anios.length - 1]}`
  const sequia = `${agua.sequia[0]}–${agua.sequia[1]}`
  const cuando = sim
    ? `en ${sim.anios[sim.idx]} · década ${sim.replica + 1} de ${sim.replicas}`
    : anio === null
      ? `promedio ${rango}`
      : anio === 'sequia'
        ? `megasequía ${sequia}`
        : valor === null
          ? `sin dato en ${anios[anio]}`
          : `en ${anios[anio]}`

  return (
    <div className={`v-agua${sim ? ' v-agua-sim' : ''}`}>
      <div className="agua-cabeza">
        <div className={`agua-cifra agua-estado-${estado}`}>
          <b>{valor === null ? '—' : fmt(valor, decimalesCaudal(valor))}</b>
          <span>m³/s</span>
          <small>{cuando}</small>
        </div>
        <div className="agua-titulo">
          <div className="agua-estacion">
            <Desplegable etiqueta="Estación" opciones={opciones} valor={e.codigo} onCambiar={p.onEstacion} />
          </div>
          <h3>{e.rio}</h3>
          <p className="agua-veredicto">
            <span className={`agua-sello agua-estado-${estado}`}>{TEXTO_ESTADO[estado]}</span>
            <span className="agua-lugar">{[comuna, e.altitud !== null ? `${fmt(e.altitud, 0)} m de altitud` : null].filter(Boolean).join(' · ')}</span>
            {fraccion !== null && (
              <span>
                <b>{fmt(fraccion * 100, 0)} %</b> de lo normal ({fmt(normal, decimalesCaudal(normal))} m³/s, promedio {agua.base[0]}–{agua.base[1]})
              </span>
            )}
          </p>
        </div>
      </div>

      {cauce && cauce.comunas.length > 0 && (
        <section className="agua-pasa" aria-label="Comunas por donde pasa">
          <ol>
            <li className="agua-pasa-titulo">
              Pasa por {cauce.comunas.length === 1 ? 'una comuna' : `${cauce.comunas.length} comunas`}
              {cauce.largoKm !== null && `, ${fmt(cauce.largoKm, 0)} km`}:
            </li>
            {(todas || cauce.comunas.length <= 5 ? cauce.comunas : [...cauce.comunas.slice(0, 2), null, ...cauce.comunas.slice(-1)]).map((c) =>
              c === null ? (
                <li key="mas" className="agua-pasa-mas">
                  <button type="button" onClick={() => setTodas(true)} aria-label={`Ver las ${cauce.comunas.length} comunas`}>
                    +{cauce.comunas.length - 3} más
                  </button>
                </li>
              ) : (
                <li key={c} className={c === e.comuna ? 'agua-pasa-estacion' : undefined}>
                  <button type="button" onClick={() => p.onComuna(c)} title={c === e.comuna ? 'Aquí está la estación' : undefined}>
                    {p.nombreComuna(c) ?? c}
                  </button>
                </li>
              ),
            )}
            {todas && cauce.comunas.length > 5 && (
              <li className="agua-pasa-mas">
                <button type="button" onClick={() => setTodas(false)}>
                  Ver menos
                </button>
              </li>
            )}
          </ol>
        </section>
      )}

      {sim ? <Simulado {...p} sim={sim} normal={normal} /> : <Medido {...p} normal={normal} rango={rango} />}
    </div>
  )
}

/** Lo medido: una barra por año, el régimen y la variabilidad. */
function Medido({ agua, estacion: e, anio, jugando, onAnio, onJugar, onSim, normal, rango }: Props & { normal: number; rango: string }) {
  const anios = agua.anios
  const reg = regimenDe(e.regimen)
  const max = Math.max(e.medio, ...e.anual.map((v) => v ?? 0)) || 1
  const paso = W / anios.length
  const y = (v: number) => (H - PIE) * (1 - v / max)
  const iSequia = Math.max(0, anios.indexOf(agua.sequia[0]))
  const maxMes = Math.max(...e.regimen) || 1
  const [detalle, setDetalle] = useState(false)
  return (
    <>
      <section className="agua-serie" aria-label="Caudal de cada año">
        <div className="agua-serie-cabeza">
          <div className="agua-periodos" role="group" aria-label="Qué período se mira">
            <button type="button" className="accion-ligera" aria-pressed={anio === 'sequia'} onClick={() => onAnio('sequia')}>
              Megasequía
            </button>
            <button type="button" className="accion-ligera" aria-pressed={anio === null} onClick={() => onAnio(null)}>
              Promedio
            </button>
            <button type="button" className="accion-ligera agua-anios" aria-pressed={jugando} onClick={() => onJugar(!jugando)}>
              <IconoJugar jugando={jugando} />
              {typeof anio === 'number' ? anios[anio] : 'Año por año'}
            </button>
          </div>
          <button type="button" className="agua-jugar" onClick={() => onSim('megasequia')}>
            ¿Y si sigue la megasequía?
          </button>
        </div>
        <svg className="agua-barras" viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`Caudal medio anual de ${e.nombre}, ${rango}`}>
          <rect className={`agua-franja${anio === 'sequia' ? ' agua-franja-activa' : ''}`} x={iSequia * paso} y={0} width={W - iSequia * paso} height={H - PIE} />
          <text className="agua-franja-texto" x={iSequia * paso + 4} y={10}>
            megasequía
          </text>
          {e.anual.map((v, i) => {
            const clase = `agua-barra agua-estado-${estadoCaudal(fraccionNormal(e, i))}${i === anio ? ' agua-barra-elegida' : ''}`
            const alto = v === null ? 3 : Math.max(2, H - PIE - y(v))
            return (
              <g key={anios[i]} className={clase} onClick={() => onAnio(i)}>
                <title>{v === null ? `${anios[i]}: sin dato` : `${anios[i]}: ${fmt(v, decimalesCaudal(v))} m³/s`}</title>
                <rect className="agua-barra-zona" x={i * paso} y={0} width={paso} height={H - PIE} />
                <rect className="agua-barra-cuerpo" x={i * paso + paso * 0.14} y={H - PIE - alto} width={paso * 0.72} height={alto} />
              </g>
            )
          })}
          <line className="agua-linea-base" x1={0} x2={W} y1={y(normal)} y2={y(normal)} />
          <text className="agua-linea-texto" x={2} y={Math.max(9, y(normal) - 3)}>
            lo normal
          </text>
          {anios.map((a, i) =>
            a % 10 === 0 || i === anios.length - 1 ? (
              <text key={a} className="agua-eje" x={i * paso + paso / 2} y={H - 2} textAnchor="middle">
                {a}
              </text>
            ) : null,
          )}
        </svg>
      </section>

      <button type="button" className="agua-detalle" aria-expanded={detalle} onClick={() => setDetalle((x) => !x)}>
        <span>
          {reg.texto} · {variabilidad(e.cv).toLowerCase()}
        </span>
        <span aria-hidden="true">{detalle ? 'Ocultar' : 'Ver detalle'}</span>
      </button>
      {detalle && (
      <div className="agua-doble">
        <section className="agua-regimen" aria-label="Régimen: caudal medio de cada mes">
          <h4>{reg.texto}</h4>
          <ol className="agua-meses" aria-hidden="true">
            {e.regimen.map((v, i) => (
              <li key={i} className={i === reg.mesAlto ? 'agua-mes-alto' : undefined}>
                <i style={{ height: `${Math.max(6, (v / maxMes) * 100)}%` }} />
                <span>{MESES_CORTOS[i]}</span>
              </li>
            ))}
          </ol>
        </section>
        <section className="agua-variable">
          <h4>
            {variabilidad(e.cv)}
            {e.vivo && (
              <a className="accion-ligera" href={e.vivo} target="_blank" rel="noopener noreferrer">
                En vivo ↗
              </a>
            )}
          </h4>
          <p>
            {e.cv !== null && (
              <>
                Varía {fmt(e.cv * 100, 0)} % mes a mes.{' '}
              </>
            )}
            Mes más seco: {fmt((e.regimen[reg.mesBajo]! / maxMes) * 100, 0)} % del mayor.
          </p>
        </section>
      </div>
      )}
    </>
  )
}

const HS = 66

/** ¿Qué pasaría si…?: la década que se reproduce sobre la banda de las 500, y lo que dicen todas. */
function Simulado({ sim, onSim, onOtraDecada, onAnioSim, normal }: Props & { sim: SimAgua; normal: number }) {
  const n = sim.anios.length
  const paso = W / n
  const tope = Math.max(1.15, ...sim.resumen.p90, ...sim.decada) * 1.05
  const x = (i: number) => i * paso + paso / 2
  const y = (f: number) => (HS - PIE) * (1 - Math.min(f, tope) / tope)
  const banda = [...sim.resumen.p90.map((v, i) => `${x(i)},${y(v)}`), ...sim.resumen.p10.map((v, i) => `${x(i)},${y(v)}`).reverse()].join(' ')
  const linea = sim.decada.map((v, i) => `${x(i)},${y(v)}`).join(' ')
  const prob = sim.resumen.probCritico[sim.idx] ?? 0
  return (
    <>
      <section className="agua-serie" aria-label="Décadas posibles de caudal">
        <div className="agua-serie-cabeza">
          <div className="agua-periodos" role="radiogroup" aria-label="¿Qué pasaría si…?">
            {ESCENARIOS_AGUA.map((s) => (
              <button key={s.id} type="button" role="radio" aria-checked={s.id === sim.escenario} className="accion-ligera" title={s.detalle} onClick={() => onSim(s.id)}>
                {s.titulo}
              </button>
            ))}
          </div>
          <button type="button" className="accion-ligera" onClick={() => onSim(null)}>
            Ver lo medido
          </button>
        </div>
        <svg className="agua-barras agua-decada" viewBox={`0 0 ${W} ${HS}`} role="group" aria-label={`Caudal simulado ${sim.anios[0]}–${sim.anios[n - 1]}, sobre lo normal`}>
          <rect className="agua-zona-critica" x={0} y={y(CORTE_CRITICO)} width={W} height={HS - PIE - y(CORTE_CRITICO)} />
          <text className="agua-franja-texto" x={3} y={HS - PIE - 3}>
            crítico
          </text>
          <polygon className="agua-banda" points={banda} />
          <line className="agua-linea-base" x1={0} x2={W} y1={y(1)} y2={y(1)} />
          <text className="agua-linea-texto" x={3} y={Math.max(9, y(1) - 3)}>
            lo normal
          </text>
          <polyline className="agua-linea-decada" points={linea} />
          {sim.decada.map((v, i) => (
            <g key={sim.anios[i]} className={`agua-punto-anio agua-estado-${estadoCaudal(v)}${i === sim.idx ? ' agua-punto-elegido' : ''}`} onClick={() => onAnioSim(i)}>
              <title>{`${sim.anios[i]}: ${fmt(v * normal, decimalesCaudal(v * normal))} m³/s, ${fmt(v * 100, 0)} % de lo normal`}</title>
              <rect className="agua-barra-zona" x={i * paso} y={0} width={paso} height={HS - PIE} />
              <circle cx={x(i)} cy={y(v)} r={i === sim.idx ? 5 : 3.2} />
              <text className="agua-eje" x={x(i)} y={HS - 2} textAnchor="middle">
                {sim.anios[i]}
              </text>
            </g>
          ))}
        </svg>
      </section>

      <div className="agua-resultado">
        <p className="agua-dato">
          <b>{fmt(sim.resumen.racha3 * 100, 0)} %</b>
          <span>
            de las {sim.replicas} décadas simuladas tienen tres años críticos seguidos. En promedio, {fmt(sim.resumen.aniosCriticos, 1)} de {n} años quedan en
            caudal crítico; en {sim.anios[sim.idx]}, el {fmt(prob * 100, 0)} % de las décadas.
          </span>
        </p>
        <button type="button" className="agua-jugar" onClick={onOtraDecada}>
          Otra década posible
        </button>
      </div>
      <p className="agua-sim-pie">Banda: 8 de cada 10 décadas. Sorteo de años medidos por la DGA; no es un pronóstico del clima.</p>
    </>
  )
}
