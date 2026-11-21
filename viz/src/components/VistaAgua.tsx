import { decimalesCaudal, MESES_CORTOS, regimenDe, TEXTO_TONO, tonoCambio, variabilidad, type Agua, type CauceDato, type Estacion } from '../lib/agua'
import { fmt } from '../lib/format'
import { Desplegable } from './Desplegable'
import { IconoJugar } from './Papel'

interface Props {
  agua: Agua
  estacion: Estacion
  /** el río mapeado: por qué comunas pasa; null si no está en el archivo */
  cauce: CauceDato | null
  onComuna: (codigo: string) => void
  /** año mostrado como índice de `agua.anios`; null = promedio del período */
  idxAnio: number | null
  jugando: boolean
  onAnio: (i: number | null) => void
  onJugar: (v: boolean) => void
  onEstacion: (codigo: string) => void
  nombreComuna: (codigo: string | null) => string | null
}

const W = 400
const H = 54
const PIE = 14

/**
 * Caudal real de un río: cuánta agua trae, cómo le fue en la megasequía, en qué meses llega y qué tan parejo es.
 * Elegir un año, o reproducirlos, encoge o ensancha los ríos del mapa.
 */
export function VistaAgua({ agua, estacion: e, cauce, onComuna, idxAnio, jugando, onAnio, onJugar, onEstacion, nombreComuna }: Props) {
  const anios = agua.anios
  const valorAnio = idxAnio === null ? null : (e.anual[idxAnio] ?? null)
  const valor = idxAnio === null ? e.medio : valorAnio
  const tono = tonoCambio(e.cambio)
  const reg = regimenDe(e.regimen)
  const comuna = nombreComuna(e.comuna)
  const max = Math.max(e.medio, ...e.anual.map((v) => v ?? 0)) || 1
  const paso = W / anios.length
  const y = (v: number) => (H - PIE) * (1 - v / max)
  const iSequia = Math.max(0, anios.indexOf(agua.sequia[0]))
  const maxMes = Math.max(...e.regimen) || 1
  const opciones = agua.estaciones.map((x) => ({ id: x.codigo, titulo: x.nombre, detalle: `${fmt(x.medio, decimalesCaudal(x.medio))} m³/s${x.cambio !== null ? ` · ${fmt(x.cambio, 0)} % en la megasequía` : ''}` }))
  const rango = `${anios[0]}–${anios[anios.length - 1]}`

  return (
    <div className="v-agua">
      <div className="agua-cabeza">
        <div className={`agua-cifra agua-tono-${tono}`}>
          <b>{valor === null ? '—' : fmt(valor, decimalesCaudal(valor))}</b>
          <span>m³/s</span>
          <small>{idxAnio === null ? `promedio ${rango}` : valor === null ? `sin dato en ${anios[idxAnio]}` : `en ${anios[idxAnio]}`}</small>
        </div>
        <div className="agua-titulo">
          <div className="agua-estacion">
            <Desplegable etiqueta="Estación" opciones={opciones} valor={e.codigo} onCambiar={onEstacion} />
          </div>
          <h3>{e.rio}</h3>
          <p className="agua-veredicto">
            <span className={`agua-sello agua-tono-${tono}`}>{TEXTO_TONO[tono]}</span>
            <span className="agua-lugar">{[comuna, e.altitud !== null ? `${fmt(e.altitud, 0)} m de altitud` : null].filter(Boolean).join(' · ')}</span>
            {e.cambio !== null && e.base !== null && e.sequia !== null && (
              <span>
                <b>{fmt(e.cambio, 0)} %</b> en la megasequía: de {fmt(e.base, decimalesCaudal(e.base))} a {fmt(e.sequia, decimalesCaudal(e.sequia))} m³/s
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
            {cauce.comunas.map((c) => (
              <li key={c} className={c === e.comuna ? 'agua-pasa-estacion' : undefined}>
                <button type="button" onClick={() => onComuna(c)} title={c === e.comuna ? 'Aquí está la estación' : undefined}>
                  {nombreComuna(c) ?? c}
                </button>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="agua-serie" aria-label="Caudal de cada año">
        <div className="agua-serie-cabeza">
          <h4>Caudal de cada año</h4>
          <div className="agua-serie-botones">
            {e.vivo && !jugando && idxAnio === null && (
              <a className="accion-ligera" href={e.vivo} target="_blank" rel="noopener noreferrer">
                Caudal de hoy ↗
              </a>
            )}
            {idxAnio !== null && !jugando && (
              <button type="button" className="accion-ligera" onClick={() => onAnio(null)}>
                Ver el promedio
              </button>
            )}
            <button type="button" className="agua-jugar" aria-pressed={jugando} onClick={() => onJugar(!jugando)}>
              <IconoJugar jugando={jugando} />
              {jugando ? 'Pausar' : 'Ver secarse los ríos'}
            </button>
          </div>
        </div>
        <svg className="agua-barras" viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`Caudal medio anual de ${e.nombre}, ${rango}`}>
          <rect className="agua-franja" x={iSequia * paso} y={0} width={W - iSequia * paso} height={H - PIE} />
          <text className="agua-franja-texto" x={iSequia * paso + 4} y={10}>
            megasequía
          </text>
          {e.anual.map((v, i) => {
            const elegido = i === idxAnio
            const clase = `agua-barra${i >= iSequia ? ' agua-barra-seca' : ''}${elegido ? ' agua-barra-elegida' : ''}${v === null ? ' agua-barra-vacia' : ''}`
            const alto = v === null ? 3 : Math.max(2, H - PIE - y(v))
            return (
              <g key={anios[i]} className={clase} onClick={() => onAnio(i)}>
                <title>{v === null ? `${anios[i]}: sin dato` : `${anios[i]}: ${fmt(v, decimalesCaudal(v))} m³/s`}</title>
                <rect className="agua-barra-zona" x={i * paso} y={0} width={paso} height={H - PIE} />
                <rect className="agua-barra-cuerpo" x={i * paso + paso * 0.14} y={H - PIE - alto} width={paso * 0.72} height={alto} />
              </g>
            )
          })}
          {e.base !== null && (
            <>
              <line className="agua-linea-base" x1={0} x2={W} y1={y(e.base)} y2={y(e.base)} />
              <text className="agua-linea-texto" x={2} y={Math.max(9, y(e.base) - 3)}>
                promedio {agua.base[0]}–{agua.base[1]}
              </text>
            </>
          )}
          {anios.map((a, i) => (a % 10 === 0 || i === anios.length - 1 ? <text key={a} className="agua-eje" x={i * paso + paso / 2} y={H - 2} textAnchor="middle">{a}</text> : null))}
        </svg>
      </section>

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
          <h4>{variabilidad(e.cv)}</h4>
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
    </div>
  )
}
