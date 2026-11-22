/**
 * Las variables que le importan a quien quiere invertir o instalar una empresa, además de las tres que
 * simula el modelo de comunas. Salen de dos fuentes. Entran al índice de riesgo solo en un caso de empresa o inversión, con peso medio (App.tsx):
 * - datos/inversion.json (datos/viz/build_inversion.py): datos reales por comuna (DGA, Coordinador, SEIA);
 * - el bloque `clima` de la simulación: cambio simulado de la frecuencia de sequía (ARClim).
 * Son archivos externos: se validan campo por campo y lo que no calza se descarta.
 */
import { riesgoPorPosicion } from './riesgo'

export interface IndicadorInversion {
  id: string
  nombre: string
  /** qué mide, en una frase */
  que: string
  unidad: string
  mejor: 'menor' | 'mayor'
  fuente: string
  periodo: string
  /** simulado por el modelo o dato real medido */
  origen: 'simulado' | 'real'
  valores: ReadonlyMap<string, number>
  /** riesgo de 0 a 100 por comuna: porcentaje de las otras comunas que están mejor */
  riesgo: ReadonlyMap<string, number>
}

type Obj = Record<string, unknown>
const esObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)
const esNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const texto = (v: unknown, max = 90): string => (typeof v === 'string' ? v.replace(/\s+/g, ' ').trim().slice(0, max) : '')
const esCodigo = (v: unknown): v is string => typeof v === 'string' && /^\d{4,5}$/.test(v)

/** Un indicador sirve para comparar si cubre al menos la mitad de las comunas y no vale lo mismo en todas. */
const MIN_COMUNAS = 26

function armar(base: Omit<IndicadorInversion, 'riesgo'>): IndicadorInversion | null {
  if (base.valores.size < MIN_COMUNAS || new Set(base.valores.values()).size < 2) return null
  return { ...base, riesgo: riesgoPorPosicion(base.valores, base.mejor) }
}

/** Lee datos/inversion.json. Descarta los indicadores que no sirven para comparar comunas. */
export function leerInversion(raw: unknown): IndicadorInversion[] {
  if (!esObj(raw) || !Array.isArray(raw.indicadores) || !Array.isArray(raw.comunas)) return []
  const out: IndicadorInversion[] = []
  for (const d of raw.indicadores.slice(0, 20)) {
    if (!esObj(d)) continue
    const id = texto(d.id, 40)
    const nombre = texto(d.nombre, 40)
    if (!/^[a-z_]{3,40}$/.test(id) || !nombre || (d.mejor !== 'menor' && d.mejor !== 'mayor')) continue
    const valores = new Map<string, number>()
    for (const c of raw.comunas.slice(0, 400)) {
      if (!esObj(c) || !esCodigo(c.codigo) || !esObj(c.valores)) continue
      const v = c.valores[id]
      if (esNum(v) && v >= 0 && v < 1e7) valores.set(c.codigo, v)
    }
    const ind = armar({ id, nombre, que: texto(d.que, 140), unidad: texto(d.unidad, 20), mejor: d.mejor, fuente: texto(d.fuente, 60), periodo: texto(d.periodo, 30), origen: 'real', valores })
    if (ind) out.push(ind)
  }
  return out
}

/**
 * Sequía futura del año pedido: mediana, entre las réplicas del modelo climático, del cambio en la
 * frecuencia de sequía respecto de 1991–2020 (puntos porcentuales; más es peor). null si la simulación no
 * trae el bloque de clima o el año queda fuera de él.
 */
export function indicadorSequia(clima: unknown, anio: number, escenario = 'ssp245'): IndicadorInversion | null {
  if (!esObj(clima) || !esObj(clima.por_escenario)) return null
  const esc = clima.por_escenario[escenario]
  if (!esObj(esc) || !Array.isArray(esc.anios) || !esObj(esc.riesgos)) return null
  const i = esc.anios.indexOf(anio)
  const hidrico = esc.riesgos.hidrico
  const sequia = esObj(hidrico) ? hidrico.drought_periods : undefined
  if (i < 0 || !esObj(sequia) || !esObj(sequia.por_comuna)) return null
  const valores = new Map<string, number>()
  for (const [codigo, banda] of Object.entries(sequia.por_comuna).slice(0, 400)) {
    const p50 = esObj(banda) && Array.isArray(banda.p50) ? banda.p50[i] : undefined
    if (esCodigo(codigo) && esNum(p50) && Math.abs(p50) < 1000) valores.set(codigo, p50)
  }
  return armar({
    id: 'sequia_futura',
    nombre: 'Sequía futura',
    que: `Cambio en la frecuencia de sequía hacia ${anio} frente a 1991–2020`,
    unidad: 'pp',
    mejor: 'menor',
    fuente: 'ARClim (MMA), simulado',
    periodo: String(anio),
    origen: 'simulado',
    valores,
  })
}

/** Orden en que se muestran: primero el agua, después la infraestructura y la actividad. */
const ORDEN = ['sequia_futura', 'escasez_hidrica', 'red_electrica', 'inversion_evaluada']

/** Los indicadores de inversión disponibles para un año, en orden; a lo más `max`. */
export function indicadoresInversion(reales: readonly IndicadorInversion[], clima: unknown, anio: number, max = 4): IndicadorInversion[] {
  const sequia = indicadorSequia(clima, anio)
  const todos = [...(sequia ? [sequia] : []), ...reales.filter((r) => r.id !== 'sequia_futura')]
  const pos = (id: string) => (ORDEN.indexOf(id) < 0 ? ORDEN.length : ORDEN.indexOf(id))
  return todos.sort((a, b) => pos(a.id) - pos(b.id)).slice(0, max)
}
