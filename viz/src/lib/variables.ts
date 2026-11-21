import type { Variable } from './types'

/** Nombre que se explica solo y unidad breve para las variables conocidas; las demás usan lo que trae el archivo. */
const CORTAS: Record<string, { nombre: string; unidad: string; que: string }> = {
  pm25_anual: { nombre: 'Calidad del aire', unidad: 'µg/m³', que: 'PM2,5, media anual' },
  seguridad: { nombre: 'Seguridad ciudadana', unidad: 'por 100 mil hab.', que: 'Delitos de mayor connotación social' },
  crecimiento_poblacion: { nombre: 'Crecimiento poblacional', unidad: '%', que: 'Población frente a 2024' },
}

export interface VariableCorta {
  id: string
  nombre: string
  unidad: string
  /** qué mide, en una línea */
  que: string
  mejor: Variable['mejor']
}

export function variableCorta(v: Variable): VariableCorta {
  const c = CORTAS[v.id]
  return { id: v.id, nombre: c?.nombre ?? v.nombre, unidad: c?.unidad ?? v.unidad, que: c?.que ?? v.nombre, mejor: v.mejor }
}
