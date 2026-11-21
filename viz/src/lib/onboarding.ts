import { textoPosicion, type Riesgo } from './riesgo'

/**
 * Entrada guiada: quién busca, qué pesa más y, si quiere, su caso en una frase.
 * Las prioridades de cada perfil son un punto de partida editable, no un dato del modelo.
 */
export type PerfilId = 'vivienda' | 'empresa' | 'explorar'

export interface Perfil {
  id: PerfilId
  titulo: string
  bajada: string
  /** prioridad de 0 a 10 por id de variable; las que falten parten en 5 */
  prioridades: Record<string, number>
  /** qué le importaría a este perfil y el modelo no mide */
  falta?: string
  /** ejemplo de caso para el campo de texto */
  ejemplo: string
}

export const PERFILES: readonly Perfil[] = [
  {
    id: 'vivienda',
    titulo: 'Comprar una vivienda',
    bajada: 'Dónde conviene vivir en los próximos diez años.',
    prioridades: { pm25_anual: 7, seguridad: 8, crecimiento_poblacion: 3 },
    falta: 'El modelo no mide precios, colegios ni transporte.',
    ejemplo: 'Busco departamento para mi familia; mi hijo tiene asma.',
  },
  {
    id: 'empresa',
    titulo: 'Invertir o instalar una empresa',
    bajada: 'Dónde el entorno juega a favor de una inversión larga.',
    prioridades: { pm25_anual: 3, seguridad: 6, crecimiento_poblacion: 9 },
    falta: 'El modelo no mide suelo, agua, energía ni conectividad.',
    ejemplo: 'Quiero instalar una planta y necesito que la zona gane población.',
  },
  {
    id: 'explorar',
    titulo: 'Solo quiero explorar',
    bajada: 'Ver el mapa con las tres variables por igual.',
    prioridades: { pm25_anual: 5, seguridad: 5, crecimiento_poblacion: 5 },
    ejemplo: '',
  },
]

/** Cinco grados en vez de una escala de once: menos que decidir. */
export const GRADOS: readonly { valor: number; texto: string }[] = [
  { valor: 0, texto: 'Nada' },
  { valor: 3, texto: 'Poco' },
  { valor: 5, texto: 'Medio' },
  { valor: 8, texto: 'Mucho' },
  { valor: 10, texto: 'Clave' },
]

/** Grado más cercano a una prioridad de 0 a 10. */
export function gradoDe(v: number): number {
  return GRADOS.reduce((m, g) => (Math.abs(g.valor - v) < Math.abs(m.valor - v) ? g : m)).valor
}

/** Prioridades de un perfil solo para las variables que existen, ya en grados. */
export function prioridadesDe(perfil: Perfil, ids: readonly string[]): Record<string, number> {
  return Object.fromEntries(ids.map((id) => [id, gradoDe(perfil.prioridades[id] ?? 5)]))
}

export const LARGO_CASO = 400

interface VarNombre {
  id: string
  nombre: string
}

/**
 * Explicación sin modelo de lenguaje: quién encabeza, en qué destaca dentro de lo que la persona
 * prioriza y quiénes siguen. Solo usa números del índice.
 */
export function explicar(riesgo: Riesgo, variables: readonly VarNombre[], pesos: Readonly<Record<string, number>>, nombre: (codigo: string) => string, falta?: string): string {
  const top = riesgo.filas.filter((f) => f.indice !== null).slice(0, 3)
  const a = top[0]
  if (!a) return 'No hay datos suficientes para ordenar las comunas.'
  const clave = variables
    .filter((v) => (pesos[v.id] ?? 0) > 0 && a.partes[v.id] !== undefined)
    .sort((x, y) => (pesos[y.id] ?? 0) - (pesos[x.id] ?? 0) || a.partes[x.id]! - a.partes[y.id]!)[0]
  let t = `${nombre(a.codigo)} es la de menor riesgo para ti`
  if (clave) t += `: ${textoPosicion(a.partes[clave.id]!)} en ${clave.nombre.toLowerCase()}`
  t += '.'
  if (top.length === 3) t += ` Le siguen ${nombre(top[1]!.codigo)} y ${nombre(top[2]!.codigo)}.`
  if (falta) t += ` ${falta}`
  return t
}
