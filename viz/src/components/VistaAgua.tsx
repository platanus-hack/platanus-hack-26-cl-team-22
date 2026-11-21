import {
  caudalEn,
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
import { fmt } from '../lib/format'
import { Desplegable } from './Desplegable'
import { IconoJugar } from './Papel'

interface Props {
  agua: Agua
  estacion: Estacion
  /** el río mapeado: por qué comunas pasa; null si no está en el archivo */
  cauce: CauceDato | null
  onComuna: (codigo: string) => void
  /** qué se mira: el promedio (null), la megasequía o un año (índice de `agua.anios`) */
  anio: AnioAgua
  jugando: boolean
  onAnio: (a: AnioAgua) => void
  onJugar: (v: boolean) => void
  onEstacion: (codigo: string) => void
  nombreComuna: (codigo: string | null) => string | null
}

const W = 400
const H = 54
const PIE = 14

/**
 * Caudal real de un río: cuánta agua trae frente a lo normal, por dónde pasa, en qué meses llega y qué tan
 * parejo es. La cifra, el sello y las barras toman el color del estado del caudal (normal, bajo o crítico),
 * igual que el río y su punto en el mapa.
 */
export function VistaAgua({ agua, estacion: e, cauce, onComuna, anio, jugando, onAnio, onJugar, onEstacion, nombreComuna }: Props) {
  const anios = agua.anios
  const valor = caudalEn(e, anio)
  const fraccion = fraccionNormal(e, anio)
  const estado = estadoCaudal(fraccion)
  const normal = e.base ?? e.medio
  const reg = regimenDe(e.regimen)
  const comuna = nombreComuna(e.comuna)
  const max = Math.max(e.medio, ...e.anual.map((v) => v ?? 0)) || 1
  const paso = W / anios.length
  const y = (v: number) => (H - PIE) * (1 - v / max)
  const iSequia = Math.max(0, anios.indexOf(agua.sequia[0]))
  const maxMes = Math.max(...e.regimen) || 1
  const opciones = agua.estaciones.map((x) => ({
    id: x.codigo,
    titulo: x.nombre,
    detalle: `${fmt(x.medio, decimalesCaudal(x.medio))} m³/s${x.cambio !== null ? ` · ${fmt(x.cambio, 0)} % en la megasequía` : ''}`,
  }))
  const rango = `${anios[0]}–${anios[anios.length - 1]}`
  const sequia = `${agua.sequia[0]}–${agua.sequia[1]}`
  const cuando = anio === null ? `promedio ${rango}` : anio === 'sequia' ? `megasequía ${sequia}` : valor === null ? `sin dato en ${anios[anio]}` : `en ${anios[anio]}`

  return (
    <div className="v-agua">
      <div className="agua-cabeza">
        <div className={`agua-cifra agua-estado-${estado}`}>
          <b>{valor === null ? '—' : fmt(valor, decimalesCaudal(valor))}</b>
          <span>m³/s</span>
          <small>{cuando}</small>
        </div>
        <div className="agua-titulo">
          <div className="agua-estacion">
            <Desplegable etiqueta="Estación" opciones={opciones} valor={e.codigo} onCambiar={onEstacion} />
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
          <div className="agua-periodos" role="group" aria-label="Qué período se mira">
            <button type="button" className="accion-ligera" aria-pressed={anio === 'sequia'} onClick={() => onAnio('sequia')}>
              Megasequía
            </button>
            <button type="button" className="accion-ligera" aria-pressed={anio === null} onClick={() => onAnio(null)}>
              Promedio
            </button>
            {typeof anio === 'number' && <span className="agua-anio-actual">{anios[anio]}</span>}
          </div>
          <button type="button" className="agua-jugar" aria-pressed={jugando} onClick={() => onJugar(!jugando)}>
            <IconoJugar jugando={jugando} />
            {jugando ? 'Pausar' : 'Ver año por año'}
          </button>
        </div>
        <svg className="agua-barras" viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`Caudal medio anual de ${e.nombre}, ${rango}`}>
          <rect className={`agua-franja${anio === 'sequia' ? ' agua-franja-activa' : ''}`} x={iSequia * paso} y={0} width={W - iSequia * paso} height={H - PIE} />
          <text className="agua-franja-texto" x={iSequia * paso + 4} y={10}>
            megasequía
          </text>
          {e.anual.map((v, i) => {
            const elegido = i === anio
            const clase = `agua-barra agua-estado-${estadoCaudal(fraccionNormal(e, i))}${elegido ? ' agua-barra-elegida' : ''}`
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
    </div>
  )
}
