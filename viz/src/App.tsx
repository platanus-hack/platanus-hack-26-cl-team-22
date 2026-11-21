import { useCallback, useEffect, useMemo, useState } from 'react'
import { ControlesVista, type ModoMapa } from './components/ControlesVista'
import { ControlTiempo } from './components/ControlTiempo'
import { FichaComuna } from './components/FichaComuna'
import { Leyenda } from './components/Leyenda'
import { ListaRanking } from './components/ListaRanking'
import { MapaComunas, type Arco, type Encuadre, type HoverInfo, type LineaOrigen, type ModoDiferencia } from './components/MapaComunas'
import { PanelPoliticas } from './components/PanelPoliticas'
import { PERSONALIZADO, PerfilHogar } from './components/PerfilHogar'
import { leerDivergente, leerRampa } from './lib/color'
import { dominio as calcDominio, punto, type Punto, variablesConDato } from './lib/data'
import { diferenciasPorComuna, maxAbsDiferencia } from './lib/diferencia'
import { fmtBanda, fmtSigned } from './lib/format'
import { seleccionarOrigenes } from './lib/origen'
import { limitesDeVista } from './lib/vista'
import { anotar, emparejar, featuresDeRespaldo, leerFeatures, type GeoFeature } from './lib/geo'
import { rankear, type FilaValores } from './lib/scoring'
import { alternar, escenarioInicial, resolverSeleccion } from './lib/scenario'
import type { Escenario, Simulacion } from './lib/types'

interface Props {
  data: Simulacion
  geoRaw: unknown
}

/** Metros de altura por unidad de variable: el máximo del dominio llega a ~4 km en pantalla. */
const ALTURA_MAX_M = 4000

export function Simulador({ data, geoRaw }: Props) {
  const anios = data.meta.anios
  const conDato = useMemo(() => variablesConDato(data), [data])
  const variablesMapa = useMemo(() => data.variables.filter((v) => conDato.has(v.id)), [data, conDato])

  const [idx, setIdx] = useState(0)
  const [jugando, setJugando] = useState(false)
  const [variableId, setVariableId] = useState(variablesMapa[0]?.id ?? data.variables[0]!.id)
  const [escenario, setEscenario] = useState<Escenario>(() => escenarioInicial(data.escenarios))
  const [activas, setActivas] = useState<ReadonlySet<string>>(() => new Set(escenarioInicial(data.escenarios).politicas_activas))
  const [calculada, setCalculada] = useState(true)
  const [seleccionada, setSeleccionada] = useState<string | null>(null)
  const [perfilId, setPerfilId] = useState(data.tipos_hogar[0]?.id ?? PERSONALIZADO)
  const [pesos, setPesos] = useState<Record<string, number>>(() => ({ ...(data.tipos_hogar[0]?.pesos ?? {}) }))
  const [mostrarArcos, setMostrarArcos] = useState(true)
  const [hover, setHover] = useState<HoverInfo | null>(null)
  const [encuadre, setEncuadre] = useState<Encuadre>('gran-santiago')
  const [reinicio, setReinicio] = useState(0)
  const [modo, setModo] = useState<ModoMapa>('valor')

  const variable = data.variables.find((v) => v.id === variableId) ?? data.variables[0]!
  const base = data.escenarios.find((e) => e.id === 'base')
  const rampa = useMemo(() => leerRampa(), [])
  const paletaDiv = useMemo(() => leerDivergente(), [])

  // Reproducción: un paso cada 700 ms; se detiene en el último año.
  useEffect(() => {
    if (!jugando) return
    const t = window.setInterval(() => {
      setIdx((i) => {
        if (i >= anios.length - 1) {
          setJugando(false)
          return i
        }
        return i + 1
      })
    }, 700)
    return () => window.clearInterval(t)
  }, [jugando, anios.length])

  // Polígonos: emparejados con el JSON; si no hay GeoJSON, círculos en lat/lon.
  const { features, hayPoligonos } = useMemo(() => {
    const reales = leerFeatures(geoRaw)
    if (reales.length === 0) return { features: featuresDeRespaldo(data.comunas), hayPoligonos: false }
    const pares = emparejar(data.comunas, reales)
    return { features: anotar(reales, pares) as GeoFeature[], hayPoligonos: true }
  }, [geoRaw, data.comunas])

  const limites = useMemo(() => limitesDeVista(features), [features])

  const dominio = useMemo(() => calcDominio(data, variable.id), [data, variable.id])

  // Diferencia: solo tiene sentido si el escenario activo no es el de referencia.
  const puedeDiferencia = base !== undefined && escenario.id !== base.id
  const diferencia = useMemo<ModoDiferencia | null>(() => {
    if (!base || !puedeDiferencia || modo !== 'diferencia') return null
    return {
      valores: diferenciasPorComuna(data, escenario.id, base.id, variable.id, idx),
      max: maxAbsDiferencia(data, escenario.id, base.id, variable.id),
      paleta: paletaDiv,
    }
  }, [data, base, puedeDiferencia, modo, escenario.id, variable.id, idx, paletaDiv])

  const puntos = useMemo(() => {
    const m = new Map<string, Punto>()
    for (const c of data.comunas) {
      const p = punto(data, escenario.id, c.codigo, variable.id, idx)
      if (p) m.set(c.codigo, p)
    }
    return m
  }, [data, escenario.id, variable.id, idx])

  const ranking = useMemo(() => {
    const filas: FilaValores[] = data.comunas.map((c) => {
      const valores: Record<string, number | undefined> = {}
      for (const v of conDato) valores[v] = punto(data, escenario.id, c.codigo, v, idx)?.p50
      return { codigo: c.codigo, valores }
    })
    return rankear(filas, data.variables, pesos)
  }, [data, escenario.id, idx, pesos, conDato])

  const arcos = useMemo<Arco[]>(() => {
    if (!mostrarArcos) return []
    const lista = data.flujos?.[escenario.id] ?? []
    const anio = anios[idx]
    const pos = new Map(data.comunas.map((c) => [c.codigo, [c.lon, c.lat] as [number, number]]))
    const out: Arco[] = []
    for (const f of lista) {
      if (f.anio !== anio) continue
      const a = pos.get(f.origen)
      const b = pos.get(f.destino)
      if (a && b) out.push({ desde: a, hasta: b, hogares: f.hogares })
    }
    return out
  }, [mostrarArcos, data, escenario.id, anios, idx])

  // Origen del aire de la comuna seleccionada: solo si el archivo trae el dato para este escenario.
  const origen = useMemo(
    () => (seleccionada ? seleccionarOrigenes(data.origen_aire?.[escenario.id]?.[seleccionada], seleccionada) : null),
    [data, escenario.id, seleccionada],
  )
  const lineasOrigen = useMemo<LineaOrigen[]>(() => {
    if (!origen || !seleccionada) return []
    const pos = new Map(data.comunas.map((c) => [c.codigo, [c.lon, c.lat] as [number, number]]))
    const destino = pos.get(seleccionada)
    if (!destino) return []
    const out: LineaOrigen[] = []
    for (const o of origen.otros) {
      const desde = pos.get(o.origen)
      if (desde) out.push({ desde, hasta: destino, fraccion: o.fraccion })
    }
    return out
  }, [origen, seleccionada, data.comunas])

  const alternarPolitica = useCallback(
    (id: string) => {
      const nuevas = alternar(activas, id)
      const sel = resolverSeleccion(data.escenarios, nuevas, escenario)
      setActivas(nuevas)
      setEscenario(sel.escenario)
      setCalculada(sel.calculada)
    },
    [activas, data.escenarios, escenario],
  )

  const elegirPerfil = (id: string) => {
    setPerfilId(id)
    const t = data.tipos_hogar.find((x) => x.id === id)
    if (t) setPesos({ ...t.pesos })
  }
  const cambiarPeso = (v: string, valor: number) => {
    setPesos((p) => ({ ...p, [v]: valor }))
    setPerfilId(PERSONALIZADO)
  }

  const comunaSel = seleccionada ? data.comunas.find((c) => c.codigo === seleccionada) : undefined
  const hovered = hover?.codigo ? data.comunas.find((c) => c.codigo === hover.codigo) : undefined
  const hoverPunto = hovered ? puntos.get(hovered.codigo) : undefined
  const hoverDif = hovered && diferencia ? diferencia.valores.get(hovered.codigo) : undefined
  const escalaAltura = ALTURA_MAX_M / (diferencia ? diferencia.max : Math.max(1, dominio[1]))

  return (
    <div className="app">
      <div className="mapa">
        <MapaComunas
          features={features}
          puntos={puntos}
          dominio={dominio}
          mejor={variable.mejor}
          rampa={rampa}
          diferencia={diferencia}
          seleccionada={seleccionada}
          arcos={arcos}
          origenes={lineasOrigen}
          escalaAltura={escalaAltura}
          limites={limites}
          encuadre={encuadre}
          reinicio={reinicio}
          onSeleccionar={setSeleccionada}
          onHover={setHover}
        />
      </div>

      <header className="panel sup">
        <div className="titulo">
          <h1>Simulador de comunas</h1>
          <span className="caps">Región Metropolitana · {anios[0]}&ndash;{anios[anios.length - 1]}</span>
          {data.meta.es_ejemplo && <span className="etiqueta-ejemplo">Datos de ejemplo</span>}
        </div>
        <PerfilHogar
          tipos={data.tipos_hogar}
          variables={data.variables}
          conDato={conDato}
          perfilId={perfilId}
          pesos={pesos}
          onPerfil={elegirPerfil}
          onPeso={cambiarPeso}
        />
        <div className="controles-mapa">
          {variablesMapa.length > 1 && (
            <>
              <label className="caps" htmlFor="var-mapa">
                Variable en el mapa
              </label>
              <select id="var-mapa" value={variable.id} onChange={(e) => setVariableId(e.target.value)}>
                {variablesMapa.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.nombre}
                  </option>
                ))}
              </select>
            </>
          )}
          <button
            type="button"
            className="boton"
            aria-pressed={mostrarArcos}
            onClick={() => setMostrarArcos((v) => !v)}
            disabled={!data.flujos}
            title={data.flujos ? undefined : 'Este archivo no trae mudanzas'}
          >
            Mudanzas {mostrarArcos ? 'visibles' : 'ocultas'}
          </button>
        </div>
      </header>

      <aside className="panel izq" aria-label="Políticas">
        <PanelPoliticas
          politicas={data.politicas}
          comunas={data.comunas}
          activas={activas}
          escenario={escenario}
          calculada={calculada}
          onAlternar={alternarPolitica}
        />
      </aside>

      <div className="centro">
        <ControlesVista
          encuadre={encuadre}
          onEncuadre={setEncuadre}
          onReiniciar={() => setReinicio((n) => n + 1)}
          modo={modo}
          onModo={setModo}
          puedeDiferencia={puedeDiferencia}
          baseNombre={base?.nombre}
        />
        {!hayPoligonos && <div className="nota-geo">Sin polígonos de comunas: se muestran círculos en su posición.</div>}
      </div>
      {hover && (
        <div
          className="tooltip"
          style={{ left: hover.x + 14, top: hover.y + 14, transform: hover.x > window.innerWidth - 480 ? "translateX(calc(-100% - 28px))" : undefined }}
          role="tooltip"
        >
          <b>{hover.nombre}</b>
          {hoverDif && base ? (
            <>
              <span className="num tt-dif">
                {fmtSigned(hoverDif.delta)} {variable.unidad}
                <small> diferencia de medianas</small>
              </span>
              <span className="num">
                {escenario.nombre}: {fmtBanda(hoverDif.activo.p50, hoverDif.activo.p10, hoverDif.activo.p90, variable.unidad)}
              </span>
              <span className="num">
                {base.nombre}: {fmtBanda(hoverDif.base.p50, hoverDif.base.p10, hoverDif.base.p90, variable.unidad)}
              </span>
            </>
          ) : (
            <span className="num">{hoverPunto ? fmtBanda(hoverPunto.p50, hoverPunto.p10, hoverPunto.p90, variable.unidad) : 'sin dato'}</span>
          )}
        </div>
      )}

      <aside className={`panel der ${comunaSel ? 'modo-ficha' : 'modo-lista'}`} aria-label={comunaSel ? 'Ficha de comuna' : 'Ranking de comunas'}>
        {comunaSel ? (
          <FichaComuna
            data={data}
            comuna={comunaSel}
            variable={variable}
            escenario={escenario}
            base={base}
            idxAnio={idx}
            origen={origen}
            onCerrar={() => setSeleccionada(null)}
          />
        ) : (
          <ListaRanking ranking={ranking} comunas={data.comunas} variables={data.variables} seleccionada={seleccionada} onSeleccionar={setSeleccionada} />
        )}
      </aside>

      <footer className="panel inf">
        <ControlTiempo anios={anios} idx={idx} jugando={jugando} onIdx={setIdx} onJugar={setJugando} />
        <Leyenda
          variable={variable}
          dominio={dominio}
          rampa={rampa}
          diferencia={diferencia && base ? { max: diferencia.max, paleta: diferencia.paleta, baseNombre: base.nombre } : null}
        />
      </footer>
    </div>
  )
}
