import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Anios, ControlesMapa, Leyenda } from './components/Marco'
import { Mapa } from './components/Mapa'
import type { Cinta, Encuadre } from './components/MapaPapel'
import { PERSONALIZADO, VistaComuna, VistaCuenca, VistaLena, VistaPlan, VistaPrueba } from './components/Vistas'
import type { AportePolitica } from './lib/capas'
import { punto, serie, variablesConDato, type Punto } from './lib/data'
import { diferenciasPorComuna, maxAbsDiferencia } from './lib/diferencia'
import { calcularHallazgos } from './lib/findings'
import { fmt, fmtBanda, fmtSigned } from './lib/format'
import { anotar, emparejar, featuresDeRespaldo, leerFeatures, type GeoFeature } from './lib/geo'
import { accionDeTecla, etiquetaModelo, pasoDemo, resumirDiferencias, vistasDisponibles } from './lib/interaccion'
import { leerLena, type Zona } from './lib/lena'
import { nivel, tablaPara } from './lib/niveles'
import { seleccionarOrigenes } from './lib/origen'
import { alternar, buscarEscenario, escenarioInicial, lecturasDisponibles, resolverSeleccion } from './lib/scenario'
import { rankear, type FilaValores } from './lib/scoring'
import type { Escenario, Simulacion } from './lib/types'

interface EstadoPlan {
  activas: ReadonlySet<string>
  escenario: Escenario
  calculada: boolean
  lectura: string | undefined
}

interface Props {
  data: Simulacion
  geoRaw: unknown
  lenaRaw: unknown
}

const ESPERA_DEMO_MS = 45_000
const PASO_DEMO_MS = 3_200
const PASO_JUGAR_MS = 900

function useMovimientoReducido(): boolean {
  const [r, setR] = useState(() => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => {
    const m = matchMedia('(prefers-reduced-motion: reduce)')
    const f = () => setR(m.matches)
    m.addEventListener('change', f)
    return () => m.removeEventListener('change', f)
  }, [])
  return r
}

export function Simulador({ data, geoRaw, lenaRaw }: Props) {
  const anios = data.meta.anios
  const conDato = useMemo(() => variablesConDato(data), [data])
  const variable = data.variables.find((v) => conDato.has(v.id)) ?? data.variables[0]!
  const tabla = useMemo(() => tablaPara(variable, data.impacto?.norma), [variable, data.impacto?.norma])
  const cortes = tabla.cortes
  const vistas = useMemo(() => vistasDisponibles(!!data.validacion), [data.validacion])
  const reducido = useMovimientoReducido()

  const inicial = useMemo(() => escenarioInicial(data.escenarios), [data.escenarios])
  const defecto = data.meta.lectura_por_defecto ?? inicial.lectura
  const lecturas = useMemo(() => lecturasDisponibles(data.escenarios, defecto), [data.escenarios, defecto])

  const [vistaIdx, setVistaIdx] = useState(0)
  const [idx, setIdx] = useState(0)
  const [jugando, setJugando] = useState(false)
  // Políticas pegadas, lectura y escenario en un solo estado: cada cambio se calcula desde el anterior,
  // así dos teclas en el mismo instante se aplican las dos.
  const [plan, setPlan] = useState<EstadoPlan>(() => ({
    activas: new Set(inicial.politicas_activas),
    escenario: inicial,
    calculada: true,
    lectura: defecto,
  }))
  const { activas, escenario, calculada, lectura } = plan
  const [modoDif, setModoDif] = useState(false)
  const [encuadre, setEncuadre] = useState<Encuadre>('gran-santiago')
  const [reencuadre, setReencuadre] = useState(0)
  const [perfilId, setPerfilId] = useState(data.tipos_hogar[0]?.id ?? PERSONALIZADO)
  const [pesos, setPesos] = useState<Record<string, number>>(() => ({ ...(data.tipos_hogar[0]?.pesos ?? {}) }))
  const [demo, setDemo] = useState(false)
  const [seleccionada, setSeleccionada] = useState<string | null>(() => {
    let mejor: string | null = null
    let v = -Infinity
    for (const c of data.comunas) {
      const p = punto(data, inicial.id, c.codigo, variable.id, 0)
      if (p && p.p50 > v) {
        v = p.p50
        mejor = c.codigo
      }
    }
    return mejor
  })

  const vista = vistas[vistaIdx]?.id ?? 'cuenca'
  const anio = anios[idx] ?? anios[0]!

  // Referencia de la diferencia: la combinación del escenario de partida, en la misma lectura.
  const referencia = useMemo(
    () => buscarEscenario(data.escenarios, new Set(inicial.politicas_activas), lectura, defecto) ?? inicial,
    [data.escenarios, inicial, lectura, defecto],
  )
  const puedeDiferencia = referencia.id !== escenario.id

  const features = useMemo<GeoFeature[]>(() => {
    const reales = leerFeatures(geoRaw)
    if (reales.length === 0) return featuresDeRespaldo(data.comunas)
    return anotar(reales, emparejar(data.comunas, reales))
  }, [geoRaw, data.comunas])

  const zonasSim = useMemo(() => {
    const m = new Map<string, Zona>()
    for (const c of data.comunas) if (c.zona_ppda === 'A' || c.zona_ppda === 'B') m.set(c.codigo, c.zona_ppda)
    return m
  }, [data.comunas])
  const lena = useMemo(() => leerLena(lenaRaw, zonasSim.size > 0 ? zonasSim : undefined), [lenaRaw, zonasSim])
  useEffect(() => {
    if (lena && lena.discrepancias.length > 0) console.warn('Zonas distintas entre lena.json y la simulación:', lena.discrepancias.join(', '))
  }, [lena])

  const nombre = useCallback((codigo: string) => data.comunas.find((c) => c.codigo === codigo)?.nombre ?? codigo, [data.comunas])

  const puntos = useMemo(() => {
    const m = new Map<string, Punto>()
    for (const c of data.comunas) {
      const p = punto(data, escenario.id, c.codigo, variable.id, idx)
      if (p) m.set(c.codigo, p)
    }
    return m
  }, [data, escenario.id, variable.id, idx])

  const difs = useMemo(
    () => (puedeDiferencia ? diferenciasPorComuna(data, escenario.id, referencia.id, variable.id, idx) : null),
    [data, puedeDiferencia, escenario.id, referencia.id, variable.id, idx],
  )
  const difMax = useMemo(
    () => (puedeDiferencia ? maxAbsDiferencia(data, escenario.id, referencia.id, variable.id) : 1),
    [data, puedeDiferencia, escenario.id, referencia.id, variable.id],
  )
  const resumen = useMemo(() => (difs ? resumirDiferencias(difs, variable.mejor, difMax) : null), [difs, variable.mejor, difMax])

  // Aporte de cada política en cada comuna: el del escenario mostrado; si allí no está (política apagada),
  // el de otro escenario que la tenga, para dibujarla despegada en su lugar.
  const aportesMapa = useMemo(() => {
    const out = new Map<string, AportePolitica[]>()
    const ap = data.aportes
    if (!ap) return out
    const misma = data.escenarios.filter((e) => (e.lectura ?? defecto) === (lectura ?? defecto)).map((e) => e.id)
    const orden = [escenario.id, ...misma, ...Object.keys(ap)]
    for (const c of data.comunas) {
      const lista: AportePolitica[] = []
      data.politicas.forEach((pol, indice) => {
        for (const esc of orden) {
          const a = ap[esc]?.[c.codigo]?.[variable.id]?.find((x) => x.politica_id === pol.id)
          if (a) {
            lista.push({ politicaId: pol.id, indice, delta: a.delta_p50_final })
            break
          }
        }
      })
      if (lista.length > 0) out.set(c.codigo, lista)
    }
    return out
  }, [data, escenario.id, lectura, defecto, variable.id])

  const origen = useMemo(
    () => (seleccionada ? seleccionarOrigenes(data.origen_aire?.[escenario.id]?.[seleccionada], seleccionada) : null),
    [data.origen_aire, escenario.id, seleccionada],
  )
  const cintas = useMemo<Cinta[]>(
    () => (vista === 'cuenca' && origen ? origen.otros.map((o) => ({ desde: o.origen, fraccion: o.fraccion })) : []),
    [vista, origen],
  )

  const ranking = useMemo(() => {
    const filas: FilaValores[] = data.comunas.map((c) => {
      const valores: Record<string, number | undefined> = {}
      for (const v of conDato) valores[v] = punto(data, escenario.id, c.codigo, v, idx)?.p50
      return { codigo: c.codigo, valores }
    })
    return rankear(filas, data.variables, pesos)
  }, [data, escenario.id, idx, pesos, conDato])

  // ---- acciones ----
  const alternarPolitica = useCallback(
    (id: string) =>
      setPlan((p) => {
        const nuevas = alternar(p.activas, id)
        const sel = resolverSeleccion(data.escenarios, nuevas, p.escenario, p.lectura, defecto)
        return { ...p, activas: nuevas, escenario: sel.escenario, calculada: sel.calculada }
      }),
    [data.escenarios, defecto],
  )
  const elegirLectura = (l: string) =>
    setPlan((p) => {
      const sel = resolverSeleccion(data.escenarios, p.activas, p.escenario, l, defecto)
      return { ...p, lectura: l, escenario: sel.escenario, calculada: sel.calculada }
    })

  // Al entrar a la leña se ve toda la región (la Zona B es la periferia); al salir vuelve el encuadre anterior.
  const encuadrePrevio = useRef<Encuadre>('gran-santiago')
  const irAVista = useCallback(
    (i: number) => {
      const destino = vistas[i]?.id
      if (!destino) return
      if (destino === 'lena' && vista !== 'lena') {
        encuadrePrevio.current = encuadre
        setEncuadre('region')
      } else if (destino !== 'lena' && vista === 'lena') {
        setEncuadre(encuadrePrevio.current)
      }
      setVistaIdx(i)
    },
    [vistas, vista, encuadre],
  )

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
    }, PASO_JUGAR_MS)
    return () => window.clearInterval(t)
  }, [jugando, anios.length])

  // ---- demostración automática ----
  const ultimo = useRef({ alternarPolitica, irAVista })
  ultimo.current = { alternarPolitica, irAVista }
  const estadoActual = useRef(plan)
  estadoActual.current = plan
  const fotoDemo = useRef<EstadoPlan | null>(null)
  const demoRef = useRef(false)
  demoRef.current = demo
  const politicaDemo = useMemo(() => {
    const i = data.politicas.findIndex((p) => !inicial.politicas_activas.includes(p.id))
    return data.politicas.length === 0 ? null : i >= 0 ? i : 0
  }, [data.politicas, inicial])

  const espera = useRef<number | null>(null)
  const actividad = useCallback(() => {
    if (demoRef.current) {
      const f = fotoDemo.current
      if (f) {
        setPlan(f)
        fotoDemo.current = null
      }
      setDemo(false)
    }
    if (espera.current !== null) window.clearTimeout(espera.current)
    espera.current = window.setTimeout(() => {
      fotoDemo.current = estadoActual.current
      setJugando(false)
      setDemo(true)
    }, ESPERA_DEMO_MS)
  }, [])

  useEffect(() => {
    actividad()
    const ev = ['pointerdown', 'pointermove', 'wheel'] as const
    for (const e of ev) window.addEventListener(e, actividad, { passive: true })
    return () => {
      for (const e of ev) window.removeEventListener(e, actividad)
      if (espera.current !== null) window.clearTimeout(espera.current)
    }
  }, [actividad])

  useEffect(() => {
    if (!demo) return
    let n = 0
    const ids = vistas.map((v) => v.id)
    const t = window.setInterval(() => {
      n++
      const paso = pasoDemo(n, ids, anios.length, politicaDemo)
      setIdx(paso.anio)
      ultimo.current.irAVista(paso.vista)
      if (paso.alternar !== null) {
        const pol = data.politicas[paso.alternar]
        if (pol) ultimo.current.alternarPolitica(pol.id)
      }
    }, PASO_DEMO_MS)
    return () => window.clearInterval(t)
  }, [demo, vistas, anios.length, politicaDemo, data.politicas])

  // ---- teclado ----
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      const enDemo = demoRef.current
      actividad()
      if (enDemo) return // la primera tecla solo detiene la demostración
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const t = e.target as HTMLElement | null
      const tag = t?.tagName
      if (tag === 'SELECT' || tag === 'TEXTAREA' || (tag === 'INPUT' && (t as HTMLInputElement).type !== 'range')) return
      if (tag === 'INPUT' && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) return
      const a = accionDeTecla(e.key, vistas.length, data.politicas.length)
      if (!a) return
      e.preventDefault()
      switch (a.tipo) {
        case 'vista':
          irAVista(a.indice)
          break
        case 'politica': {
          const pol = data.politicas[a.indice]
          if (pol) alternarPolitica(pol.id)
          break
        }
        case 'anio':
          setJugando(false)
          setIdx((i) => Math.min(anios.length - 1, Math.max(0, i + a.paso)))
          break
        case 'jugar':
          if (!jugando && idx >= anios.length - 1) setIdx(0)
          setJugando(!jugando)
          break
        case 'diferencia':
          if (puedeDiferencia) setModoDif((m) => !m)
          break
        case 'encuadre':
          setEncuadre((x) => (x === 'region' ? 'gran-santiago' : 'region'))
          break
        case 'reencuadrar':
          setReencuadre((n) => n + 1)
          break
        case 'soltar':
          setJugando(false)
          break
      }
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [actividad, vistas.length, data.politicas, irAVista, alternarPolitica, anios.length, idx, jugando, puedeDiferencia])

  // ---- textos del mapa ----
  const u = variable.unidad
  const modoMapa = vista === 'lena' ? 'lena' : vista === 'plan' && modoDif && puedeDiferencia ? 'diferencia' : 'valor'
  const textoComuna = (f: GeoFeature): { titulo: string; lineas: string[] } => {
    const titulo = f.properties.nombre
    if (modoMapa === 'lena') {
      const c = lena?.comunas.find((x) => x.codigo === f.properties.codigo)
      if (!c) return { titulo, lineas: ['Sin dato'] }
      return { titulo, lineas: [`Zona ${c.zona}`, c.toneladas === null ? 'Leña: sin dato en el RETC' : `Leña: ${fmt(c.toneladas, 1)} t de MP2,5 al año`] }
    }
    const sim = f.properties.simCodigo
    if (!sim) return { titulo, lineas: ['Sin dato'] }
    if (modoMapa === 'diferencia') {
      const d = difs?.get(sim)
      if (!d) return { titulo, lineas: ['Sin dato'] }
      return {
        titulo,
        lineas: [
          `${fmtSigned(d.delta)} ${u} de diferencia de medianas, ${anio}`,
          `${escenario.nombre}: ${fmtBanda(d.activo.p50, d.activo.p10, d.activo.p90, u)}`,
          `${referencia.nombre}: ${fmtBanda(d.base.p50, d.base.p10, d.base.p90, u)}`,
        ],
      }
    }
    const p = puntos.get(sim)
    return { titulo, lineas: [p ? `${fmtBanda(p.p50, p.p10, p.p90, u)}, ${anio}` : 'Sin dato'] }
  }
  const nombreAccesible = (f: GeoFeature) => {
    const t = textoComuna(f)
    return `${t.titulo}: ${t.lineas.join('; ')}`
  }

  // ---- hoja activa ----
  const comunaSel = seleccionada ? data.comunas.find((c) => c.codigo === seleccionada) : undefined
  const ultimoAnio = anios[anios.length - 1]!
  const nombreVariable = (id: string) => {
    const v = data.variables.find((x) => x.id === id)
    if (v) return v.nombre
    const t = id.replace(/_/g, ' ')
    return t.charAt(0).toUpperCase() + t.slice(1)
  }
  const claves = [...new Set([...data.tipos_hogar.flatMap((t) => Object.keys(t.pesos)), ...conDato])]
  const referenciaNorma =
    data.impacto?.norma !== undefined ? { valor: data.impacto.norma, texto: `norma ${fmt(data.impacto.norma, 0)} ${u}` } : undefined

  const detalle = useMemo(() => {
    if (!comunaSel) return null
    const s = serie(data, escenario.id, comunaSel.codigo, variable.id)
    if (!s) return null
    const sb = puedeDiferencia ? serie(data, referencia.id, comunaSel.codigo, variable.id) : undefined
    return {
      comuna: comunaSel,
      serie: s,
      comparacion: sb ? { nombre: referencia.nombre, p50: sb.p50 } : undefined,
      nivelBanda: s.p50[idx] !== undefined ? nivel(s.p50[idx]!, cortes) : null,
      hallazgos: calcularHallazgos({
        variable,
        anios,
        serie: s,
        escenarioNombre: escenario.nombre,
        esBase: !puedeDiferencia,
        base: sb ? { nombre: referencia.nombre, serie: sb } : undefined,
        aportes: data.aportes?.[escenario.id]?.[comunaSel.codigo]?.[variable.id],
        politicas: data.politicas,
      }),
    }
  }, [comunaSel, data, escenario, variable, puedeDiferencia, referencia, idx, cortes, anios])

  let hoja: ReactNode = null
  if (vista === 'cuenca')
    hoja = (
      <VistaCuenca
        comuna={comunaSel}
        punto={seleccionada ? puntos.get(seleccionada) : undefined}
        cortes={cortes}
        variable={variable}
        anio={anio}
        ultimoAnio={ultimoAnio}
        escenario={escenario}
        replicas={data.meta.replicas}
        origen={origen}
        nombre={nombre}
        aportes={(seleccionada && data.aportes?.[escenario.id]?.[seleccionada]?.[variable.id]) || []}
        politicas={data.politicas}
        activas={activas}
        grafico={
          detalle
            ? { anios, idxAnio: idx, serie: detalle.serie, comparacion: detalle.comparacion, referencia: referenciaNorma }
            : null
        }
      />
    )
  else if (vista === 'plan')
    hoja = (
      <VistaPlan
        politicas={data.politicas}
        comunas={data.comunas}
        activas={activas}
        escenario={escenario}
        base={referencia}
        calculada={calculada}
        significadoSin={data.meta.significado_sin}
        lecturas={lecturas.map((id) => ({ id, texto: data.meta.lecturas?.[id] ?? '' }))}
        lectura={lectura}
        onLectura={elegirLectura}
        onAlternar={alternarPolitica}
        puedeDiferencia={puedeDiferencia}
        resumen={resumen}
        variable={variable}
        anio={anio}
        nombre={nombre}
        impacto={
          data.impacto
            ? {
                metrica: data.impacto.metrica,
                norma: data.impacto.norma,
                actual: data.impacto.por_escenario[escenario.id],
                base: puedeDiferencia ? data.impacto.por_escenario[referencia.id] : undefined,
                idx,
              }
            : null
        }
      />
    )
  else if (vista === 'lena') hoja = <VistaLena lena={lena} />
  else if (vista === 'comuna')
    hoja = (
      <VistaComuna
        tipos={data.tipos_hogar}
        perfilId={perfilId}
        pesos={pesos}
        claves={claves}
        conDato={conDato}
        nombreVariable={nombreVariable}
        onPerfil={(id) => {
          setPerfilId(id)
          const t = data.tipos_hogar.find((x) => x.id === id)
          if (t) setPesos({ ...t.pesos })
        }}
        onPeso={(k, v) => {
          setPesos((p) => ({ ...p, [k]: v }))
          setPerfilId(PERSONALIZADO)
        }}
        ranking={ranking}
        nombre={nombre}
        seleccionada={seleccionada}
        onSeleccionar={setSeleccionada}
        detalle={detalle}
        anios={anios}
        idxAnio={idx}
        variable={variable}
        referencia={referenciaNorma}
      />
    )
  else if (vista === 'prueba' && data.validacion) hoja = <VistaPrueba validacion={data.validacion} aviso={data.meta.aviso} unidad={u} />

  const elegirAnio = (i: number) => {
    setJugando(false)
    setIdx(i)
  }
  const jugar = (v: boolean) => {
    if (v && idx >= anios.length - 1) setIdx(0)
    setJugando(v)
  }

  return (
    <div className={`escena${reducido ? ' quieto' : ''}`}>
      <main className="zona-mapa">
        <Mapa
          features={features}
          modo={modoMapa}
          cortes={cortes}
          puntos={puntos}
          difs={difs}
          difMax={difMax}
          mejor={variable.mejor}
          aportes={aportesMapa}
          activas={activas}
          lena={lena}
          seleccionada={seleccionada}
          cintas={cintas}
          encuadre={encuadre}
          reencuadre={reencuadre}
          reducido={reducido}
          onSeleccionar={setSeleccionada}
          etiqueta={textoComuna}
          nombreAccesible={nombreAccesible}
        >
          <ControlesMapa
            encuadre={encuadre}
            onEncuadre={setEncuadre}
            onReencuadrar={() => setReencuadre((n) => n + 1)}
            diferencia={vista === 'plan' && puedeDiferencia ? { activa: modoDif, base: referencia.nombre, onCambiar: setModoDif } : null}
          />
          <Leyenda
            modo={modoMapa}
            variable={variable}
            cortes={cortes}
            norma={tabla.norma}
            difMax={difMax}
            baseNombre={referencia.nombre}
            lena={lena}
            hayPiezas={aportesMapa.size > 0}
          />
          {demo && (
            <p className="etiqueta-demo" role="status">
              Demostración automática
            </p>
          )}
        </Mapa>
      </main>

      <section className="columna" aria-label="Lectura de la simulación">
        <header className="cabecera">
          <h1 className="marca">root</h1>
          <div className="cabecera-meta">
            {data.meta.es_ejemplo ? (
              <p className="etiqueta-ejemplo">Datos de ejemplo</p>
            ) : (
              etiquetaModelo(data.meta.modelo, data.meta.replicas, (n) => fmt(n, 0)) && (
                <p className="modelo">{etiquetaModelo(data.meta.modelo, data.meta.replicas, (n) => fmt(n, 0))}</p>
              )
            )}
          </div>
        </header>
        <nav className="pestanas" role="tablist" aria-label="Vistas">
          {vistas.map((v, i) => (
            <button
              key={v.id}
              type="button"
              role="tab"
              id={`tab-${v.id}`}
              aria-selected={i === vistaIdx}
              aria-controls="hoja"
              aria-keyshortcuts={String(i + 1)}
              className="pestana"
              onClick={() => irAVista(i)}
            >
              <span className="pestana-num">{i + 1}</span> {v.nombre}
            </button>
          ))}
        </nav>
        <div className="hoja" id="hoja" role="tabpanel" aria-labelledby={`tab-${vista}`} key={vista}>
          {hoja}
        </div>
      </section>

      <footer className="tiempo">
        <Anios
          anios={anios}
          idx={idx}
          jugando={jugando}
          onIdx={elegirAnio}
          onJugar={jugar}
          escenario={vista === 'lena' ? 'La leña: inventario 2023, no cambia con el año' : `Escenario: ${escenario.nombre}`}
        />
      </footer>
    </div>
  )
}
