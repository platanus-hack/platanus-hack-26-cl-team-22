import { fmt } from '../lib/format'
import type { Ranking } from '../lib/scoring'
import { nombreVariable } from './PerfilHogar'
import type { Comuna, Variable } from '../lib/types'

interface Props {
  ranking: Ranking
  comunas: Comuna[]
  variables: Variable[]
  seleccionada: string | null
  onSeleccionar: (codigo: string) => void
}

export function ListaRanking({ ranking, comunas, variables, seleccionada, onSeleccionar }: Props) {
  const nombre = (c: string) => comunas.find((x) => x.codigo === c)?.nombre ?? c
  return (
    <section className="ranking" aria-labelledby="h-ranking">
      <div className="ranking-cab">
      <h2 id="h-ranking" className="caps">
        Comunas según el perfil
      </h2>
      <p className="ranking-nota">
        Índice de 0 a 100 (mayor es mejor para este hogar) calculado con la mediana del año elegido; no incluye la banda.
      </p>
      <p className="ranking-nota">
        <b>Variables usadas:</b> {ranking.usadas.length > 0 ? ranking.usadas.map((k) => nombreVariable(k, variables)).join(", ") : "ninguna"}.
        {ranking.ignoradas.length > 0 && ` Se ignoran (aún sin datos): ${ranking.ignoradas.map((k) => nombreVariable(k, variables)).join(", ")}.`}
      </p>
      </div>
      <ol>
        {ranking.filas.map((f, i) => (
          <li key={f.codigo}>
            <button
              type="button"
              className="fila-ranking"
              aria-current={seleccionada === f.codigo}
              onClick={() => onSeleccionar(f.codigo)}
            >
              <span className="pos num">{i + 1}</span>
              <span>{nombre(f.codigo)}</span>
              <span className="num">{f.puntaje === null ? 'sin dato' : fmt(f.puntaje, 0)}</span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  )
}
