import type {
  Aporte,
  Aportes,
  Banda,
  BloqueValidacion,
  ComunaFocoTransformacion,
  DireccionCambio,
  Flujo,
  Impacto,
  OrigenAireMapa,
  Simulacion,
  TransformacionEscenario,
  TransformacionesMapa,
  Validacion,
} from './types'

export type Resultado = { ok: true; data: Simulacion } | { ok: false; errores: string[] }

type Obj = Record<string, unknown>

const esObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)
const esNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const esStr = (v: unknown): v is string => typeof v === 'string' && v.length > 0
const arrNum = (v: unknown): v is number[] => Array.isArray(v) && v.every(esNum)

const TOLERANCIA_SUMA = 1e-6

/**
 * Valida la clave opcional origen_aire: escenario -> comuna -> lista de {origen, fraccion}.
 * A diferencia de flujos y aportes, una entrada mal formada se rechaza con un mensaje claro,
 * porque descartarla en silencio mostraría un origen del aire incompleto como si fuera completo.
 */
export function validarOrigenAire(raw: unknown): { ok: true; valor: OrigenAireMapa } | { ok: false; errores: string[] } {
  const e: string[] = []
  const falla = (m: string) => {
    if (e.length < 6) e.push(m)
  }
  if (!esObj(raw)) return { ok: false, errores: ['"origen_aire" debe ser un objeto escenario -> comuna -> lista.'] }
  const valor: OrigenAireMapa = {}
  for (const [esc, porCom] of Object.entries(raw)) {
    if (!esObj(porCom)) {
      falla(`origen_aire.${esc} debe ser un objeto comuna -> lista.`)
      continue
    }
    const dest: OrigenAireMapa[string] = {}
    for (const [com, lista] of Object.entries(porCom)) {
      const ruta = `origen_aire.${esc}.${com}`
      if (!Array.isArray(lista)) {
        falla(`${ruta} debe ser una lista de {origen, fraccion}.`)
        continue
      }
      let suma = 0
      let bien = true
      lista.forEach((x, i) => {
        if (!esObj(x) || !esStr(x.origen) || !esNum(x.fraccion) || x.fraccion < 0 || x.fraccion > 1) {
          falla(`${ruta}[${i}] necesita origen (código de comuna) y fraccion entre 0 y 1.`)
          bien = false
        } else {
          suma += x.fraccion
        }
      })
      if (bien && suma > 1 + TOLERANCIA_SUMA) {
        falla(`${ruta}: las fracciones suman ${suma.toFixed(3)}, más que 1.`)
        bien = false
      }
      if (bien) dest[com] = lista as OrigenAireMapa[string][string]
    }
    valor[esc] = dest
  }
  return e.length > 0 ? { ok: false, errores: e } : { ok: true, valor }
}

function leerLecturas(raw: unknown): Record<string, string> | undefined {
  if (!esObj(raw)) return undefined
  const out: Record<string, string> = {}
  for (const [k, v] of Object.entries(raw)) if (esStr(k) && typeof v === 'string' && v.trim()) out[k] = v
  return Object.keys(out).length > 0 ? out : undefined
}

/** Clave opcional impacto: {metrica, norma_ugm3?, poblacion?, por_escenario: escenario -> banda por año}. Lo que no calza se descarta. */
export function leerImpacto(raw: unknown, nAnios: number): Impacto | undefined {
  if (!esObj(raw) || !esStr(raw.metrica) || !esObj(raw.por_escenario)) return undefined
  const por: Record<string, Banda> = {}
  for (const [esc, b] of Object.entries(raw.por_escenario)) {
    if (esObj(b) && arrNum(b.p10) && arrNum(b.p50) && arrNum(b.p90) && [b.p10, b.p50, b.p90].every((s) => s.length === nAnios)) {
      por[esc] = { p10: b.p10, p50: b.p50, p90: b.p90 }
    }
  }
  if (Object.keys(por).length === 0) return undefined
  return {
    metrica: raw.metrica,
    norma: esNum(raw.norma_ugm3) ? raw.norma_ugm3 : undefined,
    poblacion: typeof raw.poblacion === 'string' ? raw.poblacion : undefined,
    por_escenario: por,
  }
}

/**
 * Clave opcional validacion: bloques (objetos) de números con nombre. Solo se conservan números finitos;
 * un bloque sin ningún número se descarta. Las claves rmse_* son errores comparables dentro del bloque.
 */
export function leerValidacion(raw: unknown): Validacion | undefined {
  if (!esObj(raw)) return undefined
  const bloques: BloqueValidacion[] = []
  for (const [id, b] of Object.entries(raw)) {
    if (!esObj(b)) continue
    const valores = Object.entries(b)
      .filter((e): e is [string, number] => esNum(e[1]))
      .map(([clave, valor]) => ({ clave, valor }))
    if (valores.length > 0) bloques.push({ id, valores })
  }
  if (bloques.length === 0) return undefined
  return { fuente: typeof raw.fuente === 'string' ? raw.fuente : undefined, bloques }
}

const esDireccion = (v: unknown): v is DireccionCambio => v === 'mejora' || v === 'empeora' || v === 'neutro'

/** Clave opcional transformaciones: metadatos espacio-temporales por escenario. Lo que no calza se descarta. */
export function leerTransformaciones(raw: unknown, nAnios: number): TransformacionesMapa | undefined {
  if (!esObj(raw) || !esObj(raw.por_escenario) || nAnios <= 0) return undefined
  const por: Record<string, TransformacionEscenario> = {}
  for (const [escId, val] of Object.entries(raw.por_escenario)) {
    if (!esObj(val)) continue
    if (!esStr(val.referencia) || !esStr(val.variable) || !esStr(val.tipo) || !esNum(val.max_abs_delta)) continue
    if (!esObj(val.epicentro) || !esNum(val.epicentro.lat) || !esNum(val.epicentro.lon)) continue
    if (!arrNum(val.bbox) || val.bbox.length !== 4) continue
    if (
      !arrNum(val.intensidad_regional) ||
      val.intensidad_regional.length !== nAnios ||
      !val.intensidad_regional.every((x) => x >= 0 && x <= 1)
    ) {
      continue
    }
    if (!Array.isArray(val.comunas_foco)) continue
    const focos: ComunaFocoTransformacion[] = []
    for (const c of val.comunas_foco) {
      if (!esObj(c) || !esStr(c.codigo) || !esDireccion(c.direccion)) continue
      if (!arrNum(c.delta_p50) || c.delta_p50.length !== nAnios) continue
      if (!arrNum(c.incertidumbre) || c.incertidumbre.length !== nAnios) continue
      if (!arrNum(c.intensidad) || c.intensidad.length !== nAnios || !c.intensidad.every((x) => x >= 0 && x <= 1)) continue
      focos.push({
        codigo: c.codigo,
        direccion: c.direccion,
        delta_p50: c.delta_p50,
        incertidumbre: c.incertidumbre,
        intensidad: c.intensidad,
      })
    }
    por[escId] = {
      referencia: val.referencia,
      variable: val.variable,
      tipo: val.tipo,
      max_abs_delta: val.max_abs_delta,
      epicentro: { lat: val.epicentro.lat, lon: val.epicentro.lon },
      bbox: [val.bbox[0]!, val.bbox[1]!, val.bbox[2]!, val.bbox[3]!],
      intensidad_regional: val.intensidad_regional,
      comunas_foco: focos,
    }
  }
  if (Object.keys(por).length === 0) return undefined
  return {
    referencia_por_defecto: esStr(raw.referencia_por_defecto) ? raw.referencia_por_defecto : 'base',
    por_escenario: por,
  }
}

/**
 * Valida el JSON en la frontera. Las claves obligatorias se comprueban a fondo;
 * las opcionales (flujos, aportes, validacion) se limpian: lo que no calza se descarta.
 */
export function validarSimulacion(raw: unknown): Resultado {
  const e: string[] = []
  if (!esObj(raw)) return { ok: false, errores: ['El archivo no es un objeto JSON.'] }

  const meta = esObj(raw.meta) ? raw.meta : undefined
  if (!meta) e.push('Falta "meta".')
  const anios = meta?.anios
  if (!arrNum(anios) || anios.length === 0) e.push('"meta.anios" debe ser una lista de años.')

  const lista = (clave: string, ok: (x: Obj) => boolean, desc: string) => {
    const v = raw[clave]
    if (!Array.isArray(v) || v.length === 0 || !v.every((x) => esObj(x) && ok(x))) e.push(`"${clave}": ${desc}`)
  }
  lista(
    'variables',
    (x) => esStr(x.id) && esStr(x.nombre) && typeof x.unidad === 'string' && (x.mejor === 'menor' || x.mejor === 'mayor'),
    'cada variable necesita id, nombre, unidad y mejor (menor o mayor).',
  )
  lista(
    'comunas',
    (x) => esStr(x.codigo) && esStr(x.nombre) && esNum(x.lat) && esNum(x.lon) && esObj(x.base),
    'cada comuna necesita codigo, nombre, lat, lon y base.',
  )
  lista(
    'politicas',
    (x) =>
      esStr(x.id) &&
      esStr(x.nombre) &&
      esObj(x.credibilidad) &&
      esNum(x.credibilidad.p10) &&
      esNum(x.credibilidad.media) &&
      esNum(x.credibilidad.p90) &&
      (x.comunas === 'todas' || Array.isArray(x.comunas)),
    'cada política necesita id, nombre, comunas y credibilidad.',
  )
  lista(
    'escenarios',
    (x) => esStr(x.id) && esStr(x.nombre) && Array.isArray(x.politicas_activas) && x.politicas_activas.every(esStr),
    'cada escenario necesita id, nombre y politicas_activas.',
  )
  if (
    !Array.isArray(raw.tipos_hogar) ||
    !raw.tipos_hogar.every((x) => esObj(x) && esStr(x.id) && esStr(x.nombre) && esObj(x.pesos) && Object.values(x.pesos).every(esNum))
  ) {
    e.push('"tipos_hogar": cada tipo necesita id, nombre y pesos numéricos.')
  }

  const tray = raw.trayectorias
  if (!esObj(tray)) {
    e.push('Falta "trayectorias".')
  } else if (arrNum(anios)) {
    let n = 0
    let malas = 0
    for (const [esc, porComuna] of Object.entries(tray)) {
      if (!esObj(porComuna)) {
        e.push(`trayectorias.${esc} no es un objeto.`)
        continue
      }
      for (const [com, porVar] of Object.entries(porComuna)) {
        if (!esObj(porVar)) {
          e.push(`trayectorias.${esc}.${com} no es un objeto.`)
          continue
        }
        for (const [v, b] of Object.entries(porVar)) {
          n++
          const ok =
            esObj(b) &&
            arrNum(b.p10) &&
            arrNum(b.p50) &&
            arrNum(b.p90) &&
            b.p10.length === anios.length &&
            b.p50.length === anios.length &&
            b.p90.length === anios.length
          if (!ok && ++malas <= 5) e.push(`trayectorias.${esc}.${com}.${v}: p10, p50 y p90 deben tener un valor por año (${anios.length}).`)
        }
      }
    }
    if (malas > 5) e.push(`…y ${malas - 5} series más con el mismo problema.`)
    if (n === 0) e.push('"trayectorias" no tiene ninguna serie.')
  }

  if (raw.origen_aire !== undefined) {
    const r = validarOrigenAire(raw.origen_aire)
    if (!r.ok) e.push(...r.errores)
  }

  if (e.length > 0 || !meta) return { ok: false, errores: e.slice(0, 14) }

  const data = raw as unknown as Simulacion
  const texto = (v: unknown) => (typeof v === 'string' && v.trim() ? v : undefined)
  const out: Simulacion = {
    meta: {
      version: String(meta.version ?? ''),
      es_ejemplo: meta.es_ejemplo === true,
      anios: anios as number[],
      anio_base: esNum(meta.anio_base) ? meta.anio_base : undefined,
      aviso: texto(meta.aviso),
      modelo: texto(meta.modelo),
      replicas: esNum(meta.replicas) && meta.replicas > 0 ? meta.replicas : undefined,
      significado_sin: texto(meta.significado_sin),
      lecturas: leerLecturas(meta.lecturas),
      lectura_por_defecto: texto(meta.lectura_por_defecto),
    },
    variables: data.variables,
    comunas: data.comunas,
    tipos_hogar: data.tipos_hogar,
    politicas: data.politicas,
    escenarios: data.escenarios,
    trayectorias: data.trayectorias,
    impacto: leerImpacto(raw.impacto, (anios as number[]).length),
    validacion: leerValidacion(raw.validacion),
    transformaciones: leerTransformaciones(raw.transformaciones, (anios as number[]).length),
  }

  // Opcionales: se limpian sin fallar.
  if (esObj(raw.flujos)) {
    const fl: Record<string, Flujo[]> = {}
    for (const [esc, l] of Object.entries(raw.flujos)) {
      if (Array.isArray(l)) {
        fl[esc] = l.flatMap((f): Flujo[] => {
          if (!esObj(f) || !esNum(f.anio) || !esStr(f.origen) || !esStr(f.destino)) return []
          const personas = esNum(f.personas) ? f.personas : esNum(f.hogares) ? f.hogares : null
          return personas === null ? [] : [{ anio: f.anio, origen: f.origen, destino: f.destino, personas }]
        })
      }
    }
    out.flujos = fl
  }
  if (raw.origen_aire !== undefined) {
    const r = validarOrigenAire(raw.origen_aire)
    if (r.ok) out.origen_aire = r.valor
  }
  if (esObj(raw.aportes)) {
    const ap: Aportes = {}
    for (const [esc, porCom] of Object.entries(raw.aportes)) {
      if (!esObj(porCom)) continue
      const comunas: Record<string, Record<string, Aporte[]>> = {}
      for (const [com, porVar] of Object.entries(porCom)) {
        if (!esObj(porVar)) continue
        const dest: Record<string, Aporte[]> = {}
        for (const [v, l] of Object.entries(porVar)) {
          if (Array.isArray(l)) {
            dest[v] = l.filter((a): a is Aporte => esObj(a) && esStr(a.politica_id) && esNum(a.delta_p50_final))
          }
        }
        comunas[com] = dest
      }
      ap[esc] = comunas
    }
    out.aportes = ap
  }
  return { ok: true, data: out }
}
