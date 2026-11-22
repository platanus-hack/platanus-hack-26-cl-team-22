import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Anios, ControlesMapa, Leyenda } from './components/Marco'
import logoRoot from './assets/logo-root.png'
import { Cargando } from './components/Cargando'
import { Mapa } from './components/Mapa'
import type { AguaMapa, Cinta, Encuadre } from './components/MapaPapel'
import { VistaAgua, type SimAgua } from './components/VistaAgua'
import { decadaDe, ESCENARIOS_AGUA, REPLICAS_AGUA, resumirSim, sortearDecadas, type EscenarioAgua } from './lib/aguaSim'
import { cauceDe, claveCauce, caudalEn, decimalesCaudal, estacionDeComuna, estadoCaudal, fraccionNormal, leerAgua, TEXTO_ESTADO as TEXTO_CAUDAL, type AnioAgua, type Estacion } from './lib/agua'
import { VistaLena, VistaPlan, VistaPrueba } from './components/Vistas'
import { GENERAL, PERSONALIZADO, VistaRiesgo } from './components/VistaRiesgo'
import type { AportePolitica } from './lib/capas'
import { punto, serie, variablesConDato, type Punto } from './lib/data'
import { diferenciasPorComuna, maxAbsDiferencia } from './lib/diferencia'
import { fmt, fmtSigned } from './lib/format'
import { anotar, emparejar, featuresDeRespaldo, leerFeatures, type GeoFeature } from './lib/geo'
import { accionDeTecla, etiquetaModelo, pasoDemo, resumirDiferencias, } from './lib/interaccion'
import { comoVariables, indicadoresInversion, leerInversion, sumarIndicadores, unionIndicadores } from './lib/inversion'
import { leerLena, type Zona } from './lib/lena'
import type { Horizonte } from './lib/load'
import { CORTES_OCUPACION, bandaOcupacion, leerParametrosAbm } from './lib/mudanzasAbm'
import { useSimulacionAbm } from './lib/useSimulacionAbm'
import { VistaMudanzas, type OpcionesMudanzas } from './components/VistaMudanzas'
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
  redondear,
  ESTADO_DE_RIESGO,
  nivelRiesgo,
  TEXTO_RIESGO,
  textoPosicion,
  veredictoVariable,
  type FilaValores,
} from './lib/riesgo'
import { ordenarPorPeso, variableCorta } from './lib/variables'
import { Hoja, VistaFuentes } from './components/Hoja'
import type { VistaId } from './lib/interaccion'
import { VistaAportes } from './components/VistaAportes'
import { lugarDe, modoDe, PESTANAS, seccionesDe, type Papel, type PestanaId, type SeccionId } from './lib/pestanas'
import { Onboarding, type Busqueda } from './components/Onboarding'
import { pedirGuia, urlGuia } from './lib/guia'
import { ajustarPorTexto, casoDe, explicar, fueraDeRango, GRADOS, leerCaso, prioridadesDe, resolverLimites, sumarCambio } from './lib/onboarding'
import { aplicarAjustes, INDICADORES, LARGO_CASO_MAX, NO_MEDIDO, pedirInterpretacion, VARIABLES_CASO, type Interpretacion } from './lib/caso'
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
  aguaRaw?: { caudales: unknown; rios: unknown }
  inversionRaw?: unknown
  /** horizonte cargado y cómo pedir el otro; sin `onHorizonte` no se ofrece el cambio */
  horizonte?: Horizonte
  onHorizonte?: (h: Horizonte) => void
  cambiandoHorizonte?: boolean
}

/** cada cuánto avanza un año la reproducción de los caudales */
const PASO_AGUA_MS = 520

/** Ocupación de la vivienda (población / capacidad, %): cortes del mapa en la vista de mudanzas. */
const VARIABLE_OCUPACION = { id: 'ocupacion_vivienda', nombre: 'Ocupación de la vivienda', unidad: '% de la capacidad', mejor: 'menor' as const }

const ESPERA_DEMO_MS = 45_000
/** Dirección de la landing cuando el simulador se publica junto a ella (la fija web/scripts/incluir-simulador.mjs). */
// Link back to the landing: '../' in the published site, the landing's dev server in development (.env.development).
const inicio = (import.meta.env.VITE_INICIO_URL as string | undefined) || null
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

export function Simulador({ data, geoRaw, lenaRaw, demografiaRaw, aguaRaw, inversionRaw, horizonte = '10', onHorizonte, cambiandoHorizonte = false }: Props) {
  const anios = data.meta.anios
  const extrapolados = useMemo(() => new Set(data.meta.anios_extrapolados ?? []), [data.meta.anios_extrapolados])
  const conDato = useMemo(() => variablesConDato(data), [data])
  // El aire es la variable con norma, planes y validación; las demás hojas (plan, leña, prueba) hablan de ella.
  const varAire = data.variables.find((v) => conDato.has(v.id)) ?? data.variables[0]!
  const tabla = useMemo(() => tablaPara(varAire, data.impacto?.norma), [varAire, data.impacto?.norma])
  const cortes = tabla.cortes
  const demografia = useMemo(() => {
    if (!demografiaRaw) return null
    try {
      return leerParametrosAbm(demografiaRaw)
    } catch (e) {
      console.warn('demografia.json no se usa:', e)
      return null
    }
  }, [demografiaRaw])
  // Caudales reales de los ríos: medición histórica de la DGA, aparte de la simulación.
  const agua = useMemo(() => leerAgua(aguaRaw?.caudales, aguaRaw?.rios), [aguaRaw])
  const [aguaEstacion, setAguaEstacion] = useState<string | null>(null)
  /** qué caudal se mira: la megasequía (lo primero que se ve), el promedio (null) o un año (índice de agua.anios) */
  const [aguaAnio, setAguaAnio] = useState<AnioAgua>('sequia')
  const [aguaJugando, setAguaJugando] = useState(false)
  /** «¿qué pasaría si…?» del agua: escenario y década que se reproduce; null = se mira lo medido */
  const [aguaSim, setAguaSim] = useState<{ escenario: EscenarioAgua; replica: number } | null>(null)
  /** pantalla de espera entre la entrada y el mapa */
  const [cargando, setCargando] = useState(false)
  const [mapaListo, setMapaListo] = useState(false)
  const alListoMapa = useCallback(() => setMapaListo(true), [])
  const vistas = PESTANAS
  const reducido = useMovimientoReducido()

  const inicial = useMemo(() => escenarioInicial(data.escenarios), [data.escenarios])
  const defecto = data.meta.lectura_por_defecto ?? inicial.lectura
  const lecturas = useMemo(() => lecturasDisponibles(data.escenarios, defecto), [data.escenarios, defecto])

  const [vistaIdx, setVistaIdx] = useState(0)
  const [idx, setIdxCrudo] = useState(0)
  const setIdx: typeof setIdxCrudo = setIdxCrudo
  // Los cuatro indicadores de inversión entran al índice como variables más. Sequía futura cambia con el año
  // (bloque `clima`); escasez, red e inversión evaluada son fijos (inversion.json). Si falta un archivo, el
  // índice sigue con las variables que sí tienen dato.
  const inversionReal = useMemo(() => leerInversion(inversionRaw), [inversionRaw])
  const indsPorAnio = useMemo(() => anios.map((a) => indicadoresInversion(inversionReal, data.clima, a)), [anios, inversionReal, data.clima])
  const indicadores = useMemo(() => unionIndicadores(indsPorAnio), [indsPorAnio])
  /** las variables del índice: las simuladas y los indicadores, una sola lista para ordenar, filtrar y explicar */
  const variablesIndice = useMemo(() => [...data.variables, ...comoVariables(indicadores)], [data.variables, indicadores])
  const extrasIds = useMemo(() => new Set(indicadores.map((x) => x.id)), [indicadores])
  const cortas = useMemo(
    () => [
      ...data.variables.filter((v) => conDato.has(v.id)).map(variableCorta),
      ...indicadores.map((x) => {
        const delAnio = indsPorAnio[idx]?.find((y) => y.id === x.id) ?? x
        return { ...variableCorta(comoVariables([x])[0]!), que: `${delAnio.que}. ${x.origen === 'real' ? 'Dato real' : 'Simulado'}: ${x.fuente}` }
      }),
    ],
    [data.variables, conDato, indicadores, indsPorAnio, idx],
  )
  // Al pasar de 15 a 10 años el año elegido puede quedar fuera: se vuelve al último que existe.
  useEffect(() => {
    setIdxCrudo((i) => Math.min(i, anios.length - 1))
  }, [anios.length])
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
  /** sección abierta de cada pestaña que tiene varias */
  const [secciones, setSecciones] = useState<Partial<Record<PestanaId, SeccionId>>>({})
  /** pestañas cuya sección abierta se cerró a mano: quedan solo los títulos */
  const [plegadas, setPlegadas] = useState<ReadonlySet<PestanaId>>(new Set())
  const [demo, setDemo] = useState(false)
  // Entrada guiada: se muestra al abrir, salvo con ?directo en la dirección (para ensayar o proyectar sin ella).
  const [onb, setOnb] = useState(() => !new URLSearchParams(window.location.search).has('directo'))
  const [busqueda, setBusqueda] = useState<Busqueda | null>(null)
  /** rango aceptado por variable (id de la opción); vacío = sin límites */
  const [rangos, setRangos] = useState<Record<string, string>>({})
  const [guiaIA, setGuiaIA] = useState<{ cargando: boolean; texto?: string } | null>(null)
  // Lectura del caso por Claude: ajustes propuestos que la persona puede apagar uno por uno.
  const [lecturaCaso, setLecturaCaso] = useState<{ cargando: boolean; r?: Interpretacion; apagados: Set<string>; base: Record<string, number> } | null>(null)
  const pedido = useRef(0)
  const onbRef = useRef(onb)
  onbRef.current = onb
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

  // Pestañas por tipo de riesgo; cada una, con su sección abierta, se resuelve a la vista que dibuja panel y mapa.
  const pestana = vistas[vistaIdx] ?? vistas[0]!
  const papelVar: Record<Papel, string | undefined> = {
    aire: varAire.id,
    seguridad: conDato.has('seguridad') ? 'seguridad' : undefined,
    crecimiento: conDato.has('crecimiento_poblacion') ? 'crecimiento_poblacion' : undefined,
  }
  const disponibles = seccionesDe(pestana.id, {
    aire: true,
    seguridad: !!papelVar.seguridad,
    crecimiento: !!papelVar.crecimiento,
    lena: true,
    agua: !!agua,
    urbano: !!demografia,
    validacion: !!data.validacion,
  })
  const modo = modoDe(pestana.id, secciones[pestana.id], disponibles)
  const vista = modo.vista
  const capa = (modo.papel && papelVar[modo.papel]) || GENERAL
  /** Del resumen al detalle de una variable: abre su pestaña y su sección. */
  const irACapa = (id: string) => {
    if (id === GENERAL) return setVistaIdx(0)
    // los indicadores de inversión no tienen capa propia ni serie: no hay detalle al que ir
    if (extrasIds.has(id)) return
    const papel = (Object.keys(papelVar) as Papel[]).find((k) => papelVar[k] === id)
    if (!papel) return
    const l = lugarDe(papel)
    setSecciones((x) => ({ ...x, [l.pestana]: l.seccion }))
    setPlegadas((x) => new Set([...x].filter((k) => k !== l.pestana)))
    setVistaIdx(vistas.findIndex((v) => v.id === l.pestana))
  }
  // Una dimensión (el índice general) o una variable en detalle; fuera de la hoja de riesgo siempre es el aire.
  const variable = (vista === 'riesgo' && capa !== GENERAL && data.variables.find((v) => v.id === capa && conDato.has(v.id))) || varAire
  const esAire = variable.id === varAire.id
  // En Referencias el mapa muestra el índice general, igual que el resumen: la pestaña no trata de una variable.
  const general = (vista === 'riesgo' && capa === GENERAL) || vista === 'fuentes' || vista === 'prueba' || vista === 'aportes'
  /** el mapa pinta posición de riesgo (0 a 100) en vez del valor de la variable */
  const mapaRiesgo = general || (vista === 'riesgo' && !esAire)
  const anio = anios[idx] ?? anios[0]!

  // Simulación de mudanzas (vista 5): corre en un Web Worker solo mientras la vista está abierta.
  const [opcionesAbm, setOpcionesAbm] = useState<OpcionesMudanzas>({ semilla: 22, modoExtranjero: 'redes', eventos: [] })
  const { resultado: abm, calculando: calculandoAbm } = useSimulacionAbm(vista === 'mudanzas' ? demografia : null, opcionesAbm)
  const mapaMudanzas = vista === 'mudanzas' && !!demografia && !!abm
  const puntosMudanzas = useMemo(() => {
    const m = new Map<string, Punto>()
    if (!demografia || !abm) return m
    const t = Math.max(0, demografia.anios.indexOf(anio))
    bandaOcupacion(abm.corridas, t).forEach((b, i) => {
      if (b) m.set(demografia.comunas[i]!.codigo, b)
    })
    return m
  }, [demografia, abm, anio])

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
      sumarIndicadores(
        data.comunas.map((c) => {
          const valores: Record<string, number | undefined> = {}
          for (const v of conDato) valores[v] = punto(data, escenario.id, c.codigo, v, i)?.p50
          return { codigo: c.codigo, valores }
        }),
        indsPorAnio[i] ?? [],
      ),
    [data, escenario.id, conDato, indsPorAnio],
  )
  const riesgo = useMemo(() => calcularRiesgo(filasDe(idx), variablesIndice, pesos), [filasDe, idx, variablesIndice, pesos])
  const riesgoFin = useMemo(() => calcularRiesgo(filasDe(anios.length - 1), variablesIndice, pesos), [filasDe, anios.length, variablesIndice, pesos])

  const puntosMapa = useMemo(() => {
    if (mapaMudanzas) return puntosMudanzas
    if (!mapaRiesgo) return puntos
    const m = new Map<string, Punto>()
    for (const f of riesgo.filas) {
      const r = general ? f.indice : f.partes[variable.id]
      if (r !== null && r !== undefined) m.set(f.codigo, { p10: r, p50: r, p90: r })
    }
    return m
  }, [mapaMudanzas, puntosMudanzas, mapaRiesgo, general, puntos, riesgo, variable.id])
  const cortesMapa = mapaMudanzas ? CORTES_OCUPACION : mapaRiesgo ? CORTES_RIESGO : cortes
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
  const vistaPrevia = useRef(vista)
  useEffect(() => {
    // La leña y el agua se miran a escala de región: la Zona B es la periferia y los ríos nacen en la cordillera.
    const amplia = (v: typeof vista) => v === 'lena' || v === 'agua'
    if (amplia(vista) && !amplia(vistaPrevia.current)) {
      encuadrePrevio.current = encuadre
      setEncuadre('region')
    } else if (!amplia(vista) && amplia(vistaPrevia.current)) {
      setEncuadre(encuadrePrevio.current)
    }
    if (vista !== 'agua') setAguaJugando(false)
    vistaPrevia.current = vista
    // solo al cambiar de vista: el encuadre que se guarda es el del momento del cambio
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vista])
  // Reproducir los caudales: avanza un año por paso desde el principio y se detiene en el último.
  useEffect(() => {
    if (!aguaJugando || !agua) return
    const t = window.setInterval(() => {
      setAguaAnio((i) => {
        const sig = typeof i === 'number' ? i + 1 : 0
        if (sig >= agua.anios.length - 1) setAguaJugando(false)
        return Math.min(sig, agua.anios.length - 1)
      })
    }, PASO_AGUA_MS)
    return () => window.clearInterval(t)
  }, [aguaJugando, agua])
  const jugarAgua = (v: boolean) => {
    if (v && agua && (typeof aguaAnio !== 'number' || aguaAnio >= agua.anios.length - 1)) setAguaAnio(0)
    setAguaJugando(v)
  }
  const irAAgua = () => {
    setSecciones((x) => ({ ...x, clima: 'agua' }))
    setPlegadas((x) => new Set([...x].filter((k) => k !== 'clima')))
    setVistaIdx(vistas.findIndex((v) => v.id === 'clima'))
  }

  const irAVista = useCallback(
    (i: number) => {
      if (vistas[i]) setVistaIdx(i)
    },
    [vistas],
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
      if (onbRef.current) return // la demostración no corre detrás de la entrada guiada
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
    const ids = vistas.map((v): VistaId => (v.id === 'legal' ? 'plan' : 'riesgo'))
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
      if (onbRef.current) return // las teclas son de la entrada guiada
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
  const modoMapa = vista === 'agua' ? 'agua' : vista === 'lena' ? 'lena' : vista === 'plan' && modoDif && puedeDiferencia ? 'diferencia' : 'valor'
  const norma = data.impacto?.norma
  const textoComuna = (f: GeoFeature): Etiqueta => {
    const titulo = f.properties.nombre
    const sim = f.properties.simCodigo
    const clase = claseFondo(
      { modo: modoMapa, cortes: cortesMapa, puntos: puntosMapa, difs, difMax, mejor: mapaRiesgo || mapaMudanzas ? 'menor' : variable.mejor, lena },
      f.properties.codigo,
      sim,
    )
    if (modoMapa === 'agua') {
      const suyas = agua?.estaciones.filter((e) => e.comuna === f.properties.codigo) ?? []
      const pasan = agua?.cauces.filter((c) => c.comunas.includes(f.properties.codigo)).map((c) => c.nombre) ?? []
      const lineas = suyas.slice(0, 3).map((e) => `${e.rio}: ${fmt(e.medio, decimalesCaudal(e.medio))} m³/s`)
      if (pasan.length > 0) lineas.push(`Pasan: ${pasan.slice(0, 4).join(', ')}`)
      return { titulo, lineas: lineas.length > 0 ? lineas : ['Sin ríos mapeados'] }
    }
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
        const partes = ordenarPorPeso(cortas, pesos).filter((v) => r.partes[v.id] !== undefined && (pesos[v.id] ?? 0) > 0).map((v) => `${v.nombre} ${fmt(r.partes[v.id]!, 0)}`)
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

  // Rangos aceptados: qué comunas cumplen todos y, de la elegida, en qué variables queda fuera.
  const valoresAnio = useMemo(() => filasDe(idx), [filasDe, idx])
  const limites = useMemo(() => resolverLimites(rangos, variablesIndice, valoresAnio.map((f) => f.valores)), [rangos, variablesIndice, valoresAnio])
  const hayLimites = Object.values(limites).some((v) => v !== null)
  const dentro = useMemo(
    () => (hayLimites ? new Set(valoresAnio.filter((f) => fueraDeRango(f.valores, limites, variablesIndice).length === 0).map((f) => f.codigo)) : null),
    [hayLimites, valoresAnio, limites, variablesIndice],
  )

  /** Comunas que cumplen los rangos de una búsqueda (el estado aún no los tiene cuando se termina la entrada). */
  const cumplenDe = (b: Busqueda) => {
    const filasAnio = filasDe(idx)
    const lim = resolverLimites(b.rangos, variablesIndice, filasAnio.map((f) => f.valores))
    return new Set(filasAnio.filter((f) => fueraDeRango(f.valores, lim, variablesIndice).length === 0).map((f) => f.codigo))
  }

  /** Pide a Claude que redacte la guía de las comunas que quedan primeras con estas prioridades. */
  const pedirGuiaPara = (b: Busqueda, prioridades: Record<string, number>, n: number) => {
    const url = urlGuia(import.meta.env.VITE_GUIA_URL as string | undefined)
    if (!url || !b.contexto) return
    const cumple = cumplenDe(b)
    const filasAnio = filasDe(idx)
    const valoresDe = new Map(filasAnio.map((f) => [f.codigo, f.valores]))
    const top = calcularRiesgo(filasAnio, variablesIndice, prioridades)
      .filas.filter((f) => f.indice !== null && cumple.has(f.codigo))
      .slice(0, 3)
    const activas = ordenarPorPeso(cortas, prioridades).filter((v) => (prioridades[v.id] ?? 0) > 0)
    setGuiaIA({ cargando: true })
    void pedirGuia(url, {
      perfil: casoDe(b.caso).titulo,
      contexto: b.contexto,
      prioridades: Object.fromEntries(cortas.map((v) => [v.nombre, prioridades[v.id] ?? 0])),
      anio,
      falta: b.sinDatos.length > 0 ? `Sin datos en esta versión: ${b.sinDatos.join(', ')}.` : undefined,
      top: top.map((f) => ({
        comuna: nombre(f.codigo),
        riesgo: Math.round(f.indice!),
        variables: activas.map((v) => ({
          nombre: v.nombre,
          // the same row the index ranked (p50 or the indicator's value), rounded as the card shows it, so
          // Claude never cites 2019,985 next to a card that says 2.020
          valor: ((x) => (x === undefined ? null : redondear(x)))(valoresDe.get(f.codigo)?.[v.id]),
          unidad: v.unidad,
          riesgo: Math.round(f.partes[v.id] ?? 0),
        })),
      })),
    }).then((g) => {
      if (n !== pedido.current) return
      setGuiaIA(g ? { cargando: false, texto: g.texto } : null)
    })
  }

  /** Aplica unas prioridades: ordena, elige la primera comuna que cumple los rangos y la deja seleccionada. */
  const aplicarPrioridades = (prioridades: Record<string, number>, cumple?: ReadonlySet<string> | null) => {
    const top = calcularRiesgo(filasDe(idx), variablesIndice, prioridades).filas.find((f) => f.indice !== null && (!cumple || cumple.has(f.codigo)))
    setPesos(prioridades)
    if (top) setSeleccionada(top.codigo)
  }

  const terminarEntrada = (b: Busqueda) => {
    const cumple = cumplenDe(b)
    aplicarPrioridades(b.prioridades, cumple)
    setRangos(b.rangos)
    setPerfilId(PERSONALIZADO)
    setVistaIdx(0)
    setEncuadre('region') // las de menor riesgo suelen estar fuera del Gran Santiago
    const guiada = b.contexto !== '' || b.caso !== 'general' || b.sinDatos.length > 0 || Object.keys(b.rangos).length > 0
    setBusqueda(guiada ? b : null)
    setOnb(false)
    setCargando(true)
    setGuiaIA(null)
    setLecturaCaso(null)
    const n = ++pedido.current
    const urlCaso = urlGuia(import.meta.env.VITE_CASO_URL as string | undefined)
    if (!urlCaso || !b.contexto) return pedirGuiaPara(b, b.prioridades, n)
    // Primero Claude lee el caso y propone ajustes; el índice ordena con ellos; después se redacta la guía.
    setLecturaCaso({ cargando: true, apagados: new Set(), base: b.prioridades })
    // The entry may have read the case already (same text, profile and priorities): reuse it.
    const lectura =
      b.lectura !== undefined
        ? Promise.resolve(b.lectura)
        : pedirInterpretacion(urlCaso, { caso: b.contexto.slice(0, LARGO_CASO_MAX), perfil: casoDe(b.caso).titulo, prioridades: b.prioridades })
    void lectura.then((r) => {
      if (n !== pedido.current) return
      if (!r) {
        setLecturaCaso(null)
        return pedirGuiaPara(b, b.prioridades, n)
      }
      const nuevas = aplicarAjustes(b.prioridades, r)
      setLecturaCaso({ cargando: false, r, apagados: new Set(), base: b.prioridades })
      aplicarPrioridades(nuevas, cumple)
      pedirGuiaPara(b, nuevas, n)
    })
  }

  /**
   * Enciende o apaga un ajuste propuesto por Claude y vuelve a ordenar. Parte de las prioridades actuales, así
   * que conserva lo que la persona movió a mano; la guía de Claude hablaba de otro orden y vuelve la propia.
   */
  const alternarAjuste = (variable: string) => {
    const ajuste = lecturaCaso?.r?.ajustes.find((a) => a.variable === variable)
    if (!lecturaCaso || !ajuste) return
    const apagados = new Set(lecturaCaso.apagados)
    const encender = apagados.has(variable)
    if (encender) apagados.delete(variable)
    else apagados.add(variable)
    setLecturaCaso({ ...lecturaCaso, apagados })
    aplicarPrioridades({ ...pesos, [variable]: encender ? ajuste.grado : (lecturaCaso.base[variable] ?? pesos[variable] ?? 5) }, dentro)
    pedido.current++
    setGuiaIA(null)
  }
  const textoGrado = (g: number) => GRADOS.find((x) => x.valor === g)?.texto ?? String(g)
  const ajustesGuia =
    lecturaCaso?.r?.ajustes.map((a) => ({
      variable: a.variable,
      texto: `${cortas.find((v) => v.id === a.variable)?.nombre ?? a.variable}: ${textoGrado(a.grado)}`,
      cita: a.cita,
      activo: !lecturaCaso.apagados.has(a.variable),
    })) ?? []
  const notasGuia = lecturaCaso?.r
    ? [
        ...lecturaCaso.r.indicadores.map((k) => `Conviene mirar: ${INDICADORES[k].toLowerCase()}.`),
        ...(lecturaCaso.r.no_medido.length > 0 ? [`El modelo no mide ${lecturaCaso.r.no_medido.map((k) => NO_MEDIDO[k]).join(', ')}.`] : []),
      ]
    : []
  /**
   * Changes the request with one phrase. A phrase that describes another profile starts from that profile's
   * priorities; otherwise it starts from the current ones. The text is appended to the case so Claude, when
   * the intermediary is up, reads it whole.
   */
  const modificarBusqueda = (cambio: string) => {
    if (!busqueda) return
    const otro = leerCaso(cambio)
    const caso = casoDe(otro === 'general' ? busqueda.caso : otro)
    // same ids as the entry: every profile grades all seven variables, loaded or not
    const ids = [...new Set([...cortas.map((v) => v.id), ...VARIABLES_CASO])]
    const base = caso.id === busqueda.caso ? pesos : prioridadesDe(caso, ids)
    terminarEntrada({
      caso: caso.id,
      prioridades: ajustarPorTexto(cambio, base).prioridades,
      rangos,
      contexto: sumarCambio(busqueda.contexto, cambio, LARGO_CASO_MAX),
      sinDatos: caso.referencia.map((r) => r.nombre),
    })
  }
  const guia = busqueda
    ? {
        titulo: casoDe(busqueda.caso).titulo,
        texto:
          guiaIA?.texto ??
          (guiaIA?.cargando || lecturaCaso?.cargando
            ? 'Leyendo tu caso…'
            : explicar(riesgo, cortas, pesos, nombre, { dentro: dentro ?? undefined, sinDatos: agua ? busqueda.sinDatos.filter((x) => !/caudal/i.test(x)) : busqueda.sinDatos })),
        cargando: !!guiaIA?.cargando || !!lecturaCaso?.cargando,
        porIA: !!guiaIA?.texto,
        onCambiar: () => setOnb(true),
        onModificar: modificarBusqueda,
        onAgua: agua && busqueda.caso === 'energia' ? irAAgua : undefined,
        leyendo: !!lecturaCaso?.cargando,
        ajustes: ajustesGuia,
        notas: notasGuia,
        onAlternarAjuste: alternarAjuste,
      }
    : null

  // ---- el agua: estación elegida y lo que el mapa dibuja ----
  const nombreGeo = useCallback((codigo: string | null) => (codigo ? (features.find((f) => f.properties.codigo === codigo)?.properties.nombre ?? null) : null), [features])
  const estacion: Estacion | null = agua ? ((aguaEstacion ? agua.porCodigo.get(aguaEstacion) : undefined) ?? agua.estaciones[0] ?? null) : null
  // Al elegir una comuna en el mapa del agua se pasa a su río principal, si tiene estación.
  const comunaGeo = seleccionada ? (features.find((f) => f.properties.simCodigo === seleccionada)?.properties.codigo ?? null) : null
  useEffect(() => {
    if (vista !== 'agua' || !agua) return
    const suya = estacionDeComuna(agua.estaciones, comunaGeo)
    if (suya) setAguaEstacion((actual) => (actual && agua.porCodigo.get(actual)?.comuna === comunaGeo ? actual : suya.codigo))
    // solo al cambiar de comuna: elegir otra estación a mano no debe volver a la de la comuna
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comunaGeo, vista === 'agua'])
  const cauce = agua && estacion ? cauceDe(agua, estacion) : null
  const pasa = useMemo(() => new Set(cauce?.comunas ?? []), [cauce])
  const cauceElegido = estacion ? claveCauce(estacion.rio) : null
  /** caja del río elegido (sus tramos y su estación), para que el mapa vaya a él */
  const focoAgua = useMemo<readonly [number, number, number, number] | null>(() => {
    if (!agua || !estacion) return null
    const pts: [number, number][] = [[estacion.lon, estacion.lat]]
    for (const r of agua.rios) if (r.nombre && claveCauce(r.nombre) === cauceElegido) pts.push(...r.coords)
    const xs = pts.map((q) => q[0])
    const ys = pts.map((q) => q[1])
    const h = pts.length > 1 ? 0.02 : 0.12
    return [Math.min(...xs) - h, Math.min(...ys) - h, Math.max(...xs) + h, Math.max(...ys) + h]
  }, [agua, estacion, cauceElegido])
  // Simulación del agua: 500 décadas por escenario para los años de la línea de tiempo; se reproduce una.
  const decadas = useMemo(() => (agua && aguaSim ? sortearDecadas(agua, aguaSim.escenario, anios.length) : null), [agua, aguaSim?.escenario, anios.length])
  const decadaPorEstacion = useMemo(() => {
    const m = new Map<string, number[]>()
    if (agua && decadas && aguaSim) for (const e of agua.estaciones) m.set(e.codigo, decadaDe(agua, e, decadas, aguaSim.replica))
    return m
  }, [agua, decadas, aguaSim])
  const simVista = useMemo<SimAgua | null>(
    () =>
      agua && estacion && decadas && aguaSim
        ? {
            escenario: aguaSim.escenario,
            replica: aguaSim.replica,
            replicas: REPLICAS_AGUA,
            resumen: resumirSim(agua, estacion, decadas),
            decada: decadaPorEstacion.get(estacion.codigo) ?? [],
            anios,
            idx,
          }
        : null,
    [agua, estacion, decadas, aguaSim, decadaPorEstacion, anios, idx],
  )
  const fraccionAgua = useCallback(
    (e: Estacion) => (aguaSim ? (decadaPorEstacion.get(e.codigo)?.[idx] ?? null) : fraccionNormal(e, aguaAnio)),
    [aguaSim, decadaPorEstacion, idx, aguaAnio],
  )
  const textoCuandoAgua = !agua
    ? ''
    : aguaSim
      ? `${anio}, simulado: ${ESCENARIOS_AGUA.find((s) => s.id === aguaSim.escenario)?.titulo.toLowerCase()}`
      : aguaAnio === null
        ? `promedio ${agua.anios[0]}–${agua.anios[agua.anios.length - 1]}`
        : aguaAnio === 'sequia'
          ? `megasequía ${agua.sequia[0]}–${agua.sequia[1]}`
          : String(agua.anios[aguaAnio])
  const aguaMapa = useMemo<AguaMapa | null>(
    () =>
      agua
        ? {
            rios: agua.rios,
            estaciones: agua.estaciones,
            cauces: agua.cauces,
            pasa,
            porCodigo: agua.porCodigo,
            fraccionDe: fraccionAgua,
            caudalDe: (e) => {
              const f = fraccionAgua(e)
              return aguaSim ? (f === null ? null : f * (e.base ?? e.medio)) : caudalEn(e, aguaAnio)
            },
            clave: aguaSim ? `sim-${aguaSim.escenario}-${aguaSim.replica}-${idx}` : `medido-${aguaAnio}`,
            elegida: estacion?.codigo ?? null,
            cauceElegido,
            foco: focoAgua,
            onElegir: setAguaEstacion,
            etiqueta: (e) => {
              const f = fraccionAgua(e)
              const v = aguaSim ? (f === null ? null : f * (e.base ?? e.medio)) : caudalEn(e, aguaAnio)
              const cuando = aguaSim ? `${anio}, simulado` : aguaAnio === null ? 'promedio' : aguaAnio === 'sequia' ? 'megasequía' : String(agua.anios[aguaAnio])
              return {
                titulo: e.nombre,
                valor: v === null ? '—' : fmt(v, decimalesCaudal(v)),
                unidad: `m³/s · ${cuando}`,
                lineas: [f === null ? TEXTO_CAUDAL.sin : `${TEXTO_CAUDAL[estadoCaudal(f)]}: ${fmt(f * 100, 0)} % de lo normal`, 'Estación de medición de la DGA'],
              }
            },
          }
        : null,
    [agua, aguaAnio, aguaSim, fraccionAgua, anio, idx, estacion?.codigo, pasa, cauceElegido, focoAgua],
  )

  // Lo que la pantalla de espera dibuja; se arma una vez al abrirla, no en cada render.
  const riesgoRef = useRef(riesgo)
  riesgoRef.current = riesgo
  const mapaCarga = useMemo(
    () => ({
      features,
      rios: agua?.rios ?? [],
      clase: (f: GeoFeature) => {
        const r = f.properties.simCodigo ? riesgoRef.current.porCodigo.get(f.properties.simCodigo) : undefined
        return r && r.indice !== null ? `nivel-${papelNivel(nivel(r.indice, CORTES_RIESGO), CORTES_RIESGO)}` : null
      },
      conPlan: (f: GeoFeature) => !!f.properties.simCodigo && zonasSim.has(f.properties.simCodigo),
    }),
    // `cargando` entra para que cada apertura tome el riesgo del momento
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [features, agua, zonasSim, cargando],
  )

  let hoja: ReactNode = null
  if (vista === 'riesgo') {
    const cod = comunaSel?.codigo
    const valores: Record<string, number | undefined> = {}
    // la fila con que el índice ordenó: p50 de las simuladas y el valor de cada indicador
    if (cod) Object.assign(valores, valoresAnio.find((f) => f.codigo === cod)?.valores)
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
        onCapa={irACapa}
        tipos={data.tipos_hogar}
        perfilId={perfilId}
        pesos={pesos}
        extras={extrasIds}
        rangos={rangos}
        onRango={(k, id) => setRangos((x) => ({ ...x, [k]: id }))}
        onPerfil={(id) => {
          setPerfilId(id)
          // otro perfil: una lectura del caso todavía en camino ya no aplica
          pedido.current++
          setLecturaCaso((l) => (l?.cargando ? null : l))
          const t = data.tipos_hogar.find((x) => x.id === id)
          if (t) setPesos(aPrioridades(t.pesos))
        }}
        onPeso={(k, v) => {
          setPesos((p) => ({ ...p, [k]: v }))
          setPerfilId(PERSONALIZADO)
          // el texto de Claude hablaba de otro orden: vuelve la explicación propia
          pedido.current++
          setGuiaIA(null)
          setLecturaCaso((l) => (l?.cargando ? null : l))
        }}
        guia={guia}
        riesgo={riesgo}
        riesgoFin={riesgoFin}
        anio={anio}
        ultimoAnio={ultimoAnio}
        nombre={nombre}
        comuna={comunaSel}
        onSeleccionar={setSeleccionada}
        valores={valores}
        sellos={sellos}
        dentro={dentro}
        fuera={cod ? fueraDeRango(valores, limites, variablesIndice) : []}
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
  else if (vista === 'agua' && agua && estacion)
    hoja = (
      <VistaAgua
        agua={agua}
        estacion={estacion}
        cauce={cauce}
        onComuna={(codigo) => {
          const sim = features.find((f) => f.properties.codigo === codigo)?.properties.simCodigo
          if (sim) setSeleccionada(sim)
        }}
        anio={aguaAnio}
        jugando={aguaJugando}
        onAnio={(a) => {
          setAguaJugando(false)
          setAguaAnio(a)
        }}
        onJugar={jugarAgua}
        onEstacion={setAguaEstacion}
        nombreComuna={nombreGeo}
        sim={simVista}
        onSim={(esc) => {
          setAguaJugando(false)
          setAguaSim((s) => (esc ? { escenario: esc, replica: s?.replica ?? 0 } : null))
          if (esc && !aguaSim) {
            // al abrir la simulación la década se reproduce sola desde el primer año
            setIdx(0)
            setJugando(true)
          }
          if (!esc) setJugando(false)
        }}
        onOtraDecada={() => {
          setAguaSim((s) => (s ? { ...s, replica: (s.replica + 1) % REPLICAS_AGUA } : s))
          setIdx(0)
          setJugando(true)
        }}
        onAnioSim={(i) => {
          setJugando(false)
          setIdx(i)
        }}
      />
    )
  else if (vista === 'fuentes') hoja = <VistaFuentes politicas={data.politicas} />
  else if (vista === 'aportes') hoja = <VistaAportes codigo={comunaGeo ?? seleccionada} nombre={comunaSel?.nombre ?? ''} />
  else if (vista === 'prueba' && data.validacion) hoja = <VistaPrueba validacion={data.validacion} aviso={data.meta.aviso} unidad={u} />
  else if (vista === 'mudanzas' && demografia)
    hoja = (
      <VistaMudanzas
        datos={demografia}
        resultado={abm}
        calculando={calculandoAbm}
        opciones={opcionesAbm}
        onOpciones={setOpcionesAbm}
        anio={anio}
        seleccionada={seleccionada ? demografia.comunas.findIndex((c) => c.codigo === seleccionada) : -1}
        onSeleccionar={setSeleccionada}
      />
    )

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
          mejor={mapaRiesgo || mapaMudanzas ? 'menor' : variable.mejor}
          aportes={mapaRiesgo || mapaMudanzas ? sinAportes : aportesMapa}
          activas={activas}
          lena={lena}
          agua={aguaMapa}
          seleccionada={seleccionada}
          cintas={cintas}
          encuadre={encuadre}
          reencuadre={reencuadre}
          reducido={reducido}
          onSeleccionar={setSeleccionada}
          onListo={alListoMapa}
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
            variable={mapaMudanzas ? VARIABLE_OCUPACION : variable}
            cortes={mapaMudanzas ? cortesMapa : cortes}
            norma={mapaMudanzas ? null : tabla.norma}
            difMax={difMax}
            baseNombre={referencia.nombre}
            lena={lena}
            agua={
              modoMapa === 'agua' && agua
                ? {
                    cuando: textoCuandoAgua,
                    normal: `${agua.base[0]}–${agua.base[1]}`,
                  }
                : null
            }
            hayPiezas={aportesMapa.size > 0}
            ocupacion={mapaMudanzas}
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

      {onb && <Onboarding
          variables={cortas}
          onListo={terminarEntrada}
          inicio={inicio}
          hasta={anios[anios.length - 1]!}
          urlCaso={urlGuia(import.meta.env.VITE_CASO_URL as string | undefined)}
        />}
      {cargando && !onb && (
        <Cargando
          onFin={() => setCargando(false)}
          mapa={mapaCarga}
          pasos={[
            { texto: busqueda?.contexto ? 'Leyendo tu caso' : 'Preparando la región', listo: !lecturaCaso?.cargando },
            { texto: `Ubicando las ${data.comunas.length} comunas en el mapa`, listo: mapaListo, etapa: 'comunas' },
            ...(agua ? [{ texto: `Midiendo los ríos: ${agua.estaciones.length} estaciones de la DGA`, listo: true, etapa: 'rios' as const }] : []),
            { texto: `Revisando ${data.politicas.length} planes y normas`, listo: true, etapa: 'planes' },
            { texto: 'Ordenando las comunas por riesgo', listo: true, etapa: 'riesgo' },
          ]}
        />
      )}

      <section className="columna" aria-label="Lectura de la simulación" inert={onb || cargando}>
        <header className="cabecera">
          <h1 className="marca">
            {inicio ? (
              <a href={inicio} title="Volver al inicio">
                <img src={logoRoot} alt="root" />
              </a>
            ) : (
              <img src={logoRoot} alt="root" />
            )}
          </h1>
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
        <div className="hoja" id="hoja" role="tabpanel" aria-labelledby={`tab-${pestana.id}`} key={pestana.id}>
          <Hoja
            pestana={pestana}
            secciones={disponibles}
            abierta={plegadas.has(pestana.id) ? null : modo.seccion}
            onSeccion={(id) => {
              // tocar la sección abierta la cierra; tocar otra la abre
              const cerrar = id === modo.seccion && !plegadas.has(pestana.id)
              setPlegadas((x) => {
                const y = new Set(x)
                if (cerrar) y.add(pestana.id)
                else y.delete(pestana.id)
                return y
              })
              setSecciones((x) => ({ ...x, [pestana.id]: id }))
            }}
          >
            {hoja}
          </Hoja>
        </div>
      </section>

      <footer className="tiempo">
        <Anios
          anios={anios}
          idx={idx}
          jugando={jugando}
          onIdx={elegirAnio}
          onJugar={jugar}
          extrapolados={extrapolados}
          horizonte={onHorizonte ? { valor: horizonte, cambiando: cambiandoHorizonte, onCambiar: onHorizonte } : null}
          escenario={
            vista === 'lena'
              ? 'La leña: inventario 2023, no cambia con el año'
              : vista === 'agua'
                ? aguaSim
                  ? `Agua simulada: ${ESCENARIOS_AGUA.find((s) => s.id === aguaSim.escenario)?.titulo.toLowerCase()} · década ${aguaSim.replica + 1} de ${REPLICAS_AGUA}`
                  : 'Caudales: medición histórica, no cambia con el año'
                : `Escenario: ${escenario.nombre}`
          }
        />
      </footer>
    </div>
  )
}
