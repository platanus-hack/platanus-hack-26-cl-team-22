import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Anios, ControlesMapa, Leyenda } from './components/Marco'
import { Mapa } from './components/Mapa'
import type { Cinta, Encuadre } from './components/MapaPapel'
import { VistaLena, VistaPlan, VistaPrueba } from './components/Vistas'
import { GENERAL, PERSONALIZADO, VistaRiesgo } from './components/VistaRiesgo'
import type { AportePolitica } from './lib/capas'
import { punto, serie, variablesConDato, type Punto } from './lib/data'
import { diferenciasPorComuna, maxAbsDiferencia } from './lib/diferencia'
import { fmt, fmtSigned } from './lib/format'
import { anotar, emparejar, featuresDeRespaldo, leerFeatures, type GeoFeature } from './lib/geo'
import { accionDeTecla, etiquetaModelo, pasoDemo, resumirDiferencias, vistasDisponibles } from './lib/interaccion'
import { leerLena, type Zona } from './lib/lena'
import { leerDemografia } from './lib/demografia'
import { VistaMudanzas } from './components/VistaMudanzas'
import { estadoAire, TEXTO_ESTADO, veredictoComuna } from './lib/estado'
import { claseFondo } from './lib/fondo'
import { nivel, papelNivel, tablaPara } from './lib/niveles'
import type { Etiqueta } from './components/Papel'
import { seleccionarOrigenes } from './lib/origen'
import { alternar, buscarEscenario, escenarioInicial, lecturasDisponibles, resolverSeleccion } from './lib/scenario'
import {
  aPrioridad,
  calcularRiesgo,
  CORTES_RIESGO,
  decimales,
  ESTADO_DE_RIESGO,
  nivelRiesgo,
  TEXTO_RIESGO,
  textoPosicion,
  veredictoVariable,
  type FilaValores,
} from './lib/riesgo'
import { variableCorta } from './lib/variables'
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
  demografiaRaw?: unknown
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

export function Simulador({ data, geoRaw, lenaRaw, demografiaRaw }: Props) {
  const anios = data.meta.anios
  const conDato = useMemo(() => variablesConDato(data), [data])
  // El aire es la variable con norma, planes y validación; las demás hojas (plan, leña, prueba) hablan de ella.
  const varAire = data.variables.find((v) => conDato.has(v.id)) ?? data.variables[0]!
  const tabla = useMemo(() => tablaPara(varAire, data.impacto?.norma), [varAire, data.impacto?.norma])
  const cortas = useMemo(() => data.variables.filter((v) => conDato.has(v.id)).map(variableCorta), [data.variables, conDato])
  const cortes = tabla.cortes
  const demografia = useMemo(() => {
    if (!demografiaRaw) return null
    try {
      return leerDemografia(demografiaRaw)
    } catch (e) {
      console.warn('demografia.json no se usa:', e)
      return null
    }
  }, [demografiaRaw])
  const vistas = useMemo(() => vistasDisponibles(!!data.validacion, !!demografia), [data.validacion, demografia])
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
  const aPrioridades = (w: Record<string, number>) => Object.fromEntries(Object.entries(w).map(([k, v]) => [k, aPrioridad(v)]))
  const [pesos, setPesos] = useState<Record<string, number>>(() => aPrioridades(data.tipos_hogar[0]?.pesos ?? {}))
  const [capa, setCapa] = useState<string>(GENERAL)
  const [demo, setDemo] = useState(false)
  const [seleccionada, setSeleccionada] = useState<string | null>(() => {
    let mejor: string | null = null
    let v = -Infinity
    for (const c of data.comunas) {
      const p = punto(data, inicial.id, c.codigo, varAire.id, 0)
      if (p && p.p50 > v) {
        v = p.p50
        mejor = c.codigo
      }
    }
    return mejor
  })

  const vista = vistas[vistaIdx]?.id ?? 'riesgo'
  // Una dimensión (el índice general) o una variable en detalle; fuera de la hoja de riesgo siempre es el aire.
  const variable = (vista === 'riesgo' && capa !== GENERAL && data.variables.find((v) => v.id === capa && conDato.has(v.id))) || varAire
  const esAire = variable.id === varAire.id
  const general = vista === 'riesgo' && capa === GENERAL
  /** el mapa pinta posición de riesgo (0 a 100) en vez del valor de la variable */
  const mapaRiesgo = vista === 'riesgo' && (general || !esAire)
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
    () => (vista === 'riesgo' && !mapaRiesgo && origen ? origen.otros.map((o) => ({ desde: o.origen, fraccion: o.fraccion })) : []),
    [vista, mapaRiesgo, origen],
  )

  const filasDe = useCallback(
    (i: number): FilaValores[] =>
      data.comunas.map((c) => {
        const valores: Record<string, number | undefined> = {}
        for (const v of conDato) valores[v] = punto(data, escenario.id, c.codigo, v, i)?.p50
        return { codigo: c.codigo, valores }
      }),
    [data, escenario.id, conDato],
  )
  const riesgo = useMemo(() => calcularRiesgo(filasDe(idx), data.variables, pesos), [filasDe, idx, data.variables, pesos])
  const riesgoFin = useMemo(() => calcularRiesgo(filasDe(anios.length - 1), data.variables, pesos), [filasDe, anios.length, data.variables, pesos])

  const puntosMapa = useMemo(() => {
    if (!mapaRiesgo) return puntos
    const m = new Map<string, Punto>()
    for (const f of riesgo.filas) {
      const r = general ? f.indice : f.partes[variable.id]
      if (r !== null && r !== undefined) m.set(f.codigo, { p10: r, p50: r, p90: r })
    }
    return m
  }, [mapaRiesgo, general, puntos, riesgo, variable.id])
  const cortesMapa = mapaRiesgo ? CORTES_RIESGO : cortes
  const sinAportes = useMemo(() => new Map<string, AportePolitica[]>(), [])

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
  const norma = data.impacto?.norma
  const textoComuna = (f: GeoFeature): Etiqueta => {
    const titulo = f.properties.nombre
    const sim = f.properties.simCodigo
    const clase = claseFondo(
      { modo: modoMapa, cortes: cortesMapa, puntos: puntosMapa, difs, difMax, mejor: mapaRiesgo ? 'menor' : variable.mejor, lena },
      f.properties.codigo,
      sim,
    )
    if (modoMapa === 'lena') {
      const c = lena?.comunas.find((x) => x.codigo === f.properties.codigo)
      if (!c) return { titulo, lineas: ['Sin dato'] }
      if (c.toneladas === null) return { titulo, lineas: [`Zona ${c.zona}`, 'Sin dato en el RETC'] }
      return { titulo, valor: fmt(c.toneladas, 0), unidad: 't de MP2,5 al año', clase, lineas: [`Zona ${c.zona}`] }
    }
    if (!sim) return { titulo, lineas: ['Sin dato'] }
    if (modoMapa === 'diferencia') {
      const d = difs?.get(sim)
      if (!d) return { titulo, lineas: ['Sin dato'] }
      return {
        titulo,
        valor: fmtSigned(d.delta),
        unidad: `${u} · ${anio}`,
        clase,
        lineas: [`${escenario.nombre}: ${fmt(d.activo.p50, 1)}`, `${referencia.nombre}: ${fmt(d.base.p50, 1)}`],
      }
    }
    if (mapaRiesgo && modoMapa === 'valor') {
      const r = riesgo.porCodigo.get(sim)
      if (general) {
        if (!r || r.indice === null) return { titulo, lineas: ['Sin dato'] }
        const n = nivelRiesgo(r.indice)
        const partes = cortas.filter((v) => r.partes[v.id] !== undefined).map((v) => `${v.nombre} ${fmt(r.partes[v.id]!, 0)}`)
        return {
          titulo,
          valor: fmt(r.indice, 0),
          unidad: 'de 100',
          clase,
          estado: { id: ESTADO_DE_RIESGO[n], texto: TEXTO_RIESGO[n] },
          lineas: [`Puesto ${r.puesto} de ${riesgo.total} · ${anio}`, partes.join(' · ')],
        }
      }
      const pv = puntos.get(sim)
      const parte = r?.partes[variable.id]
      if (!pv || parte === undefined) return { titulo, lineas: ['Sin dato'] }
      const n = nivelRiesgo(parte)
      const t = textoPosicion(parte)
      return {
        titulo,
        valor: fmt(pv.p50, decimales(pv.p50)),
        unidad: variableCorta(variable).unidad,
        clase,
        estado: { id: ESTADO_DE_RIESGO[n], texto: TEXTO_RIESGO[n] },
        lineas: [`${t.charAt(0).toUpperCase()}${t.slice(1)} · ${anio}`],
      }
    }
    const p = puntos.get(sim)
    if (!p) return { titulo, lineas: ['Sin dato'] }
    const lineas = [`Banda ${fmt(p.p10, 1)}–${fmt(p.p90, 1)} · ${anio}`]
    if (norma !== undefined) lineas.push(p.p50 > norma ? `${fmtSigned(p.p50 - norma)} sobre la norma` : `${fmt(norma - p.p50, 1)} bajo la norma`)
    const est = norma !== undefined && variable.mejor === 'menor' ? estadoAire(p.p50, norma) : undefined
    return { titulo, valor: fmt(p.p50, 1), unidad: u, clase, estado: est && { id: est, texto: TEXTO_ESTADO[est] }, lineas }
  }
  const nombreAccesible = (f: GeoFeature) => {
    const t = textoComuna(f)
    return `${t.titulo}: ${[t.valor ? `${t.valor} ${t.unidad ?? ''}`.trim() : '', ...t.lineas].filter(Boolean).join('; ')}`
  }

  // ---- hoja activa ----
  const comunaSel = seleccionada ? data.comunas.find((c) => c.codigo === seleccionada) : undefined
  const ultimoAnio = anios[anios.length - 1]!
  const referenciaNorma =
    data.impacto?.norma !== undefined ? { valor: data.impacto.norma, texto: `norma ${fmt(data.impacto.norma, 0)} ${u}` } : undefined

  let hoja: ReactNode = null
  if (vista === 'riesgo') {
    const cod = comunaSel?.codigo
    const valores: Record<string, number | undefined> = {}
    if (cod) for (const v of cortas) valores[v.id] = punto(data, escenario.id, cod, v.id, idx)?.p50
    // El aire tiene norma: si la comuna la supera o la roza, eso manda sobre su posición.
    const sellos: Record<string, { estado: 'riesgo' | 'limite'; texto: string } | undefined> = {}
    const vAire = valores[varAire.id]
    if (norma !== undefined && vAire !== undefined && varAire.mejor === 'menor') {
      const e = estadoAire(vAire, norma)
      if (e === 'riesgo') sellos[varAire.id] = { estado: e, texto: 'Sobre la norma' }
      else if (e === 'limite') sellos[varAire.id] = { estado: e, texto: 'Al límite' }
    }
    const s = cod && !general ? serie(data, escenario.id, cod, variable.id) : undefined
    const sb = s && cod && puedeDiferencia ? serie(data, referencia.id, cod, variable.id) : undefined
    const pt = cod ? puntos.get(cod) : undefined
    const parte = cod ? riesgo.porCodigo.get(cod)?.partes[variable.id] : undefined
    const conNorma = esAire && norma !== undefined && variable.mejor === 'menor'
    hoja = (
      <VistaRiesgo
        variables={cortas}
        capa={general ? GENERAL : variable.id}
        onCapa={setCapa}
        tipos={data.tipos_hogar}
        perfilId={perfilId}
        pesos={pesos}
        onPerfil={(id) => {
          setPerfilId(id)
          const t = data.tipos_hogar.find((x) => x.id === id)
          if (t) setPesos(aPrioridades(t.pesos))
        }}
        onPeso={(k, v) => {
          setPesos((p) => ({ ...p, [k]: v }))
          setPerfilId(PERSONALIZADO)
        }}
        riesgo={riesgo}
        riesgoFin={riesgoFin}
        anio={anio}
        ultimoAnio={ultimoAnio}
        nombre={nombre}
        comuna={comunaSel}
        onSeleccionar={setSeleccionada}
        valores={valores}
        sellos={sellos}
        detalle={
          s
            ? {
                variable: variableCorta(variable),
                punto: pt,
                serie: s,
                comparacion: sb ? { nombre: referencia.nombre, p50: sb.p50 } : undefined,
                referencia: conNorma ? referenciaNorma : undefined,
                veredicto: conNorma
                  ? veredictoComuna(s.p50, anios, idx, norma, pt)
                  : parte !== undefined
                    ? veredictoVariable(parte, s.p50, anios, idx, variable)
                    : null,
                papel: conNorma
                  ? pt
                    ? papelNivel(nivel(pt.p50, cortes), cortes)
                    : null
                  : parte !== undefined
                    ? papelNivel(nivel(parte, CORTES_RIESGO), CORTES_RIESGO)
                    : null,
                aportes: (cod && data.aportes?.[escenario.id]?.[cod]?.[variable.id]) || [],
              }
            : null
        }
        anios={anios}
        idxAnio={idx}
        politicas={data.politicas}
      />
    )
  }
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
  else if (vista === 'prueba' && data.validacion) hoja = <VistaPrueba validacion={data.validacion} aviso={data.meta.aviso} unidad={u} />
  else if (vista === 'mudanzas' && demografia) hoja = <VistaMudanzas datos={demografia} anio={anio} />

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
          cortes={cortesMapa}
          puntos={puntosMapa}
          difs={difs}
          difMax={difMax}
          mejor={mapaRiesgo ? 'menor' : variable.mejor}
          aportes={mapaRiesgo ? sinAportes : aportesMapa}
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
            riesgo={
              mapaRiesgo && modoMapa === 'valor'
                ? { titulo: general ? 'Riesgo general, de 0 a 100' : `Riesgo en ${variableCorta(variable).nombre.toLowerCase()}, de 0 a 100`, total: riesgo.total }
                : null
            }
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
