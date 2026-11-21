export type Mejor = 'menor' | 'mayor'

export interface Variable {
  id: string
  nombre: string
  unidad: string
  mejor: Mejor
}

export interface Comuna {
  codigo: string
  nombre: string
  lat: number
  lon: number
  base: Record<string, number>
  /** zona del PPDA para la leña (A o B), si el archivo la trae */
  zona_ppda?: string
}

export interface TipoHogar {
  id: string
  nombre: string
  pesos: Record<string, number>
}

export interface Credibilidad {
  p10: number
  media: number
  p90: number
}

export interface Politica {
  id: string
  nombre: string
  nivel: string
  fuente: string
  comunas: 'todas' | string[]
  credibilidad: Credibilidad
  /** Comunal policies: each municipality's credibility (ChileCompra-updated prior), by CUT. */
  credibilidad_por_comuna?: Record<string, Credibilidad & {
    procedencia: string
    tasa_adjudicacion: number | null
    licitaciones_cerradas: number
  }>
  url?: string
  /** "vigente" o "propuesta" */
  tipo?: string
  cita?: string
  efecto?: string
}

export interface Escenario {
  id: string
  nombre: string
  politicas_activas: string[]
  /** lectura de la credibilidad (p. ej. "conservadora"); sin ella cuenta como la lectura por defecto */
  lectura?: string
}

export interface Banda {
  p10: number[]
  p50: number[]
  p90: number[]
}

/** escenario -> comuna -> variable -> banda */
export type Trayectorias = Record<string, Record<string, Record<string, Banda>>>

export interface Aporte {
  politica_id: string
  delta_p50_final: number
}

/** escenario -> comuna -> variable -> aportes */
export type Aportes = Record<string, Record<string, Record<string, Aporte[]>>>

export interface Flujo {
  anio: number
  origen: string
  destino: string
  /** Personas que se mudan (archivos antiguos lo llamaban `hogares`). */
  personas: number
}

/** Parte (0 a 1) del PM2,5 de una comuna que aportan las emisiones de la comuna de origen. */
export interface OrigenAire {
  origen: string
  fraccion: number
}

/** escenario -> comuna -> orígenes del aire (la suma puede ser menor que 1: el resto es fondo regional) */
export type OrigenAireMapa = Record<string, Record<string, OrigenAire[]>>

export type DireccionCambio = 'mejora' | 'empeora' | 'neutro'

export type TipoTransformacion =
  | 'reduccion_emisiones'
  | 'seguridad_comunal'
  | 'acople_hogares'
  | 'comparacion_credibilidad'
  | (string & {})

export interface ComunaFocoTransformacion {
  codigo: string
  direccion: DireccionCambio
  delta_p50: number[]
  incertidumbre: number[]
  intensidad: number[]
}

export interface TransformacionEscenario {
  referencia: string
  variable: string
  tipo: TipoTransformacion
  max_abs_delta: number
  epicentro: { lat: number; lon: number }
  bbox: [number, number, number, number]
  intensidad_regional: number[]
  comunas_foco: ComunaFocoTransformacion[]
  /** Present when the pattern across comunas is not validated: only the region-level change is shown. */
  aviso?: string
}

export interface TransformacionesMapa {
  referencia_por_defecto: string
  por_escenario: Record<string, TransformacionEscenario>
}

export interface Simulacion {
  meta: {
    version: string
    es_ejemplo: boolean
    anios: number[]
    anio_base?: number
    aviso?: string
    modelo?: string
    replicas?: number
    significado_sin?: string
    lecturas?: Record<string, string>
    lectura_por_defecto?: string
  }
  variables: Variable[]
  comunas: Comuna[]
  tipos_hogar: TipoHogar[]
  politicas: Politica[]
  escenarios: Escenario[]
  trayectorias: Trayectorias
  aportes?: Aportes
  flujos?: Record<string, Flujo[]>
  origen_aire?: OrigenAireMapa
  impacto?: Impacto
  validacion?: Validacion
  transformaciones?: TransformacionesMapa
}

/** Personas que viven en comunas sobre la norma, por escenario y año. */
export interface Impacto {
  metrica: string
  norma?: number
  poblacion?: string
  por_escenario: Record<string, Banda>
}

/** Un bloque de la validación: números con nombre (errores rmse_* y otros datos). */
export interface BloqueValidacion {
  id: string
  valores: { clave: string; valor: number }[]
  /** Unidad de los errores del bloque (p. ej. «personas»). Sin ella, la de la variable del mapa. */
  unidad?: string
  /** Qué se mide, en una frase. */
  metrica?: string
  /** Advertencia honesta sobre la prueba. */
  aviso?: string
}

export interface Validacion {
  fuente?: string
  bloques: BloqueValidacion[]
}
