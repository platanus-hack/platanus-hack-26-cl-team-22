import { useMemo, useState } from 'react'
import {
  COMPONENTES,
  MULTIPLICADORES_BASE,
  cambiosPorComuna,
  mayoresFlujos,
  proyectarDemografia,
  type Componente,
  type Demografia,
  type Multiplicadores,
} from '../lib/demografia'
import { fmt, fmtSigned } from '../lib/format'
import { GraficoBanda } from './GraficoBanda'

/**
 * Prototype of view 6, "Las mudanzas": the open household model runs live while the sliders move.
 * Every slider scales a measured rate (1 = what the census and vital statistics measured).
 */

const ETIQUETA: Record<Componente, string> = {
  natalidad: 'Nacimientos',
  mortalidad: 'Defunciones',
  llegan_regiones: 'Llegadas desde otras regiones',
  llegan_extranjero: 'Llegadas desde el extranjero',
  salen_regiones: 'Salidas a otras regiones',
}

const total = (fila: number[]) => fila.reduce((s, v) => s + v, 0)
const CERO: Multiplicadores = { natalidad: 0, mortalidad: 0, llegan_regiones: 0, llegan_extranjero: 0, salen_regiones: 0 }

export function VistaMudanzas({ datos, anio }: { datos: Demografia; anio: number }) {
  const [mult, setMult] = useState<Multiplicadores>(MULTIPLICADORES_BASE)
  const proy = useMemo(() => proyectarDemografia(datos, mult), [datos, mult])
  const cerrado = useMemo(() => proyectarDemografia(datos, CERO), [datos])
  const t = Math.max(0, Math.min(datos.anios.length - 1, datos.anios.indexOf(anio)))
  const codigos = datos.comunas.map((c) => c.codigo)
  const nombre = (codigo: string) => datos.comunas.find((c) => c.codigo === codigo)?.nombre ?? codigo
  const totales = proy.poblacion.map(total)
  const totalesCerrado = cerrado.poblacion.map(total)
  const millones = totales.map((v) => v / 1e6)
  const millonesCerrado = totalesCerrado.map((v) => v / 1e6)
  const cambios = cambiosPorComuna(datos.comunas, proy.poblacion, t)
  const flujos = t > 0 ? mayoresFlujos(proy.flujos[t - 1]!, codigos, 5) : []
  const anual = (c: Componente) => mult[c] * datos.tasas[c].reduce((s, r, i) => s + r * datos.poblacion_inicial[i]!, 0)

  return (
    <div className="v-prueba">
      <p className="v-escenario">
        Una simulación dentro de la simulación: la población de cada comuna cambia en vivo con las mudanzas entre comunas, los nacimientos, las
        defunciones y quienes llegan o se van de la región. Cada control escala lo que midieron el censo y las estadísticas vitales.
      </p>

      <section className="bloque" aria-labelledby="h-controles">
        <h3 id="h-controles">Controles</h3>
        {COMPONENTES.map((c) => (
          <label key={c} className="prueba-frase" style={{ display: 'grid', gridTemplateColumns: '1fr 6rem 9.5rem', gap: '0.5rem', alignItems: 'center', margin: '0.15rem 0' }}>
            <span>{ETIQUETA[c]}</span>
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={mult[c]}
              aria-label={`${ETIQUETA[c]}: ${fmt(mult[c] * 100, 0)} % de lo medido`}
              onChange={(e) => setMult({ ...mult, [c]: Number(e.target.value) })}
            />
            <span style={{ whiteSpace: 'nowrap', textAlign: 'right' }}>
              {fmt(anual(c), 0)}/año · {fmt(mult[c] * 100, 0)} %
            </span>
          </label>
        ))}
        <button type="button" onClick={() => setMult(MULTIPLICADORES_BASE)}>
          Volver a lo medido
        </button>
      </section>

      <section className="bloque" aria-labelledby="h-total">
        <h3 id="h-total">Región Metropolitana en {datos.anios[t]}</h3>
        <p className="prueba-frase">
          <b>{fmt(totales[t]!, 0)} personas</b> ({fmtSigned(((totales[t]! - totales[0]!) / totales[0]!) * 100, 1)} % desde {datos.anios[0]}). El
          modelo cerrado que usa hoy la simulación deja {fmt(totalesCerrado[t]!, 0)}.
        </p>
        <GraficoBanda
          anios={datos.anios}
          serie={{ p10: millones, p50: millones, p90: millones }}
          comparacion={{ nombre: 'Modelo cerrado', p50: millonesCerrado }}
          idxAnio={t}
          unidad="millones de personas"
          nivelBanda={null}
        />
        <p className="prueba-frase">Línea continua: con tus controles. Comparación: modelo cerrado (sin nacimientos ni migración externa).</p>
      </section>

      <section className="bloque" aria-labelledby="h-comunas">
        <h3 id="h-comunas">Las que más crecen y más bajan</h3>
        <ul className="barras">
          {[...cambios.slice(0, 4), ...cambios.slice(-3)].map((c) => (
            <li key={c.codigo}>
              <span className="barra-txt">{c.nombre}</span>
              <span className="barra-num">
                {fmtSigned(c.pct, 1)} % · {fmtSigned(c.personas, 0)} personas
              </span>
            </li>
          ))}
        </ul>
      </section>

      {flujos.length > 0 && (
        <section className="bloque" aria-labelledby="h-flujos">
          <h3 id="h-flujos">Mayores mudanzas de {datos.anios[t]}</h3>
          <ul className="barras">
            {flujos.map((f) => (
              <li key={`${f.origen}-${f.destino}`}>
                <span className="barra-txt">
                  {nombre(f.origen)} → {nombre(f.destino)}
                </span>
                <span className="barra-num">{fmt(f.personas, 0)} personas</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="bloque" aria-labelledby="h-hallazgos">
        <h3 id="h-hallazgos">Lo que medimos</h3>
        <ul>
          <li className="prueba-frase">Quienes llegan de afuera van a donde llegaron otros antes: la geografía de 2012–2017 predice la de 2019–2024 (correlación 0,93).</li>
          <li className="prueba-frase">La vivienda nueva del centro la ocupó la inmigración, no las mudanzas entre comunas (permisos y llegadas del extranjero: 0,76).</li>
          <li className="prueba-frase">Desde 2017 los nacimientos cayeron 31 %: con tasas antiguas, cualquier proyección sobreestima la población.</li>
        </ul>
        {datos.supuestos.length > 0 && <p className="aviso aviso-honesto">{datos.supuestos.join(' ')}</p>}
      </section>
    </div>
  )
}
