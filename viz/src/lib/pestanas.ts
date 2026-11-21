import type { VistaId } from './interaccion'

/**
 * Pestañas por tipo de riesgo y, dentro de cada una, secciones plegables (una abierta a la vez).
 * Cada sección se resuelve a un «modo»: la vista de siempre que dibuja el panel y el mapa,
 * y la variable que muestra si corresponde.
 */
export type PestanaId = 'resumen' | 'clima' | 'legal' | 'social' | 'referencias'
export type SeccionId = 'aire' | 'lena' | 'agua' | 'seguridad' | 'crecimiento' | 'urbano' | 'fuentes' | 'validacion'

export interface DefPestana {
  id: PestanaId
  nombre: string
  /** título y subtítulo que explican la hoja antes de los datos; el resumen no los lleva */
  titulo?: string
  subtitulo?: string
}

export const PESTANAS: readonly DefPestana[] = [
  { id: 'resumen', nombre: 'Resumen' },
  { id: 'clima', nombre: 'Climático', titulo: 'Riesgo climático y ambiental', subtitulo: 'El aire de cada comuna hasta 2036, su fuente principal y el agua de sus ríos.' },
  { id: 'legal', nombre: 'Legal', titulo: 'Marco legal y planes públicos', subtitulo: 'Qué planes afectan a cada comuna y con qué probabilidad se cumplen.' },
  { id: 'social', nombre: 'Social', titulo: 'Riesgo social', subtitulo: 'Seguridad, población y desarrollo urbano de cada comuna.' },
  { id: 'referencias', nombre: 'Referencias', titulo: 'Referencias y validación', subtitulo: 'De dónde salen los datos y cómo le fue al modelo contra lo que no había visto.' },
]

export interface DefSeccion {
  id: SeccionId
  titulo: string
}

/** Variable de la simulación que muestra cada sección, por su papel (el id real lo resuelve quien llama). */
export type Papel = 'aire' | 'seguridad' | 'crecimiento'

type Pide = 'lena' | 'agua' | 'urbano' | 'validacion' | Papel

const SECCIONES: Record<PestanaId, readonly (DefSeccion & { pide?: Pide })[]> = {
  resumen: [],
  clima: [
    { id: 'aire', titulo: 'Calidad del aire', pide: 'aire' },
    { id: 'lena', titulo: 'La leña, su fuente principal', pide: 'lena' },
    { id: 'agua', titulo: 'El agua: caudal de los ríos', pide: 'agua' },
  ],
  legal: [],
  social: [
    { id: 'seguridad', titulo: 'Seguridad ciudadana', pide: 'seguridad' },
    { id: 'crecimiento', titulo: 'Crecimiento poblacional', pide: 'crecimiento' },
    { id: 'urbano', titulo: 'Desarrollo urbano: quién se muda a dónde', pide: 'urbano' },
  ],
  referencias: [
    { id: 'fuentes', titulo: 'Fuentes de datos y normas' },
    { id: 'validacion', titulo: 'El modelo contra datos que no vio', pide: 'validacion' },
  ],
}

/** Secciones de una pestaña que tienen con qué mostrarse. */
export function seccionesDe(p: PestanaId, hay: Readonly<Partial<Record<Pide, boolean>>>): DefSeccion[] {
  return SECCIONES[p].filter((s) => !s.pide || hay[s.pide]).map(({ id, titulo }) => ({ id, titulo }))
}

export interface Modo {
  vista: VistaId | 'fuentes' | 'agua'
  /** papel de la variable en detalle; null = índice general o no aplica */
  papel: Papel | null
}

const MODOS: Partial<Record<SeccionId, Modo>> = {
  aire: { vista: 'riesgo', papel: 'aire' },
  lena: { vista: 'lena', papel: null },
  agua: { vista: 'agua', papel: null },
  seguridad: { vista: 'riesgo', papel: 'seguridad' },
  crecimiento: { vista: 'riesgo', papel: 'crecimiento' },
  urbano: { vista: 'mudanzas', papel: null },
  fuentes: { vista: 'fuentes', papel: null },
  validacion: { vista: 'prueba', papel: null },
}

/** Qué dibujar para una pestaña con su sección abierta (la primera disponible si la pedida no existe). */
export function modoDe(p: PestanaId, seccion: SeccionId | undefined, disponibles: readonly DefSeccion[]): Modo & { seccion: SeccionId | null } {
  if (p === 'resumen') return { vista: 'riesgo', papel: null, seccion: null }
  if (p === 'legal') return { vista: 'plan', papel: null, seccion: null }
  const s = disponibles.find((x) => x.id === seccion) ?? disponibles[0]
  if (!s) return { vista: p === 'referencias' ? 'fuentes' : 'riesgo', papel: null, seccion: null }
  return { ...(MODOS[s.id] ?? { vista: 'riesgo', papel: null }), seccion: s.id }
}

/** Dónde vive el detalle de una variable: pestaña y sección. */
export function lugarDe(papel: Papel): { pestana: PestanaId; seccion: SeccionId } {
  return papel === 'aire' ? { pestana: 'clima', seccion: 'aire' } : { pestana: 'social', seccion: papel }
}
