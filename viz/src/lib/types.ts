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
  url?: string
}

export interface Escenario {
  id: string
  nombre: string
  politicas_activas: string[]
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
  hogares: number
}

/** Parte (0 a 1) del PM2,5 de una comuna que aportan las emisiones de la comuna de origen. */
export interface OrigenAire {
  origen: string
  fraccion: number
}

/** escenario -> comuna -> orígenes del aire (la suma puede ser menor que 1: el resto es fondo regional) */
export type OrigenAireMapa = Record<string, Record<string, OrigenAire[]>>

export interface Simulacion {
  meta: {
    version: string
    es_ejemplo: boolean
    anios: number[]
    anio_base?: number
    aviso?: string
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
  validacion?: unknown
}
