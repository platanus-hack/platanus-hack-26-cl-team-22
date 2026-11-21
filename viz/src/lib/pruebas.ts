import type { Validacion } from './types'

/**
 * Marcador de la validación: cada prueba fuera de muestra enfrenta el error del modelo con la mejor
 * alternativa simple. Menor error es mejor.
 */
export type Resultado = 'gana' | 'empata' | 'pierde'

export interface FilaPrueba {
  id: string
  titulo: string
  modelo: number
  rival: { nombre: string; valor: number }
  resultado: Resultado
  /** cómo se muestra el error: en la unidad del aire, en personas o como porcentaje */
  formato: 'aire' | 'personas' | 'pct'
}

/** Errores que difieren menos de un 5 % cuentan como empate: 0,90 contra 0,91 no es ganar. */
export const TOLERANCIA = 0.05

export function comparar(modelo: number, rival: number, tolerancia = TOLERANCIA): Resultado {
  const ref = Math.max(Math.abs(modelo), Math.abs(rival))
  if (ref === 0 || Math.abs(modelo - rival) / ref < tolerancia) return 'empata'
  return modelo < rival ? 'gana' : 'pierde'
}

const TITULOS: Record<string, string> = {
  cambio_2017_2023: 'Aire: cambio de 2017 a 2023',
  niveles_2024: 'Aire: niveles de 2024',
  hogares: 'Mudanzas entre comunas, 2019 a 2024',
  poblacion: 'Población por comuna, 2017 a 2024',
  vivienda: 'Vivienda nueva como atractor de mudanzas',
}

const RIVALES: Record<string, string> = {
  rmse_sin_cambio: 'suponer que nada cambia',
  rmse_mismo_cambio_en_todas: 'el mismo cambio en todas',
  rmse_persistencia: 'repetir el año anterior',
  rmse_media_otras_estaciones: 'la media de las otras estaciones',
  rmse_nadie_se_muda: 'suponer que nadie se muda',
  rmse_repetir_2012_2017: 'repetir 2012 a 2017',
  persistencia_2023: 'repetir 2023',
  persistencia_2022: 'repetir 2022',
  tendencia_2022_2023: 'seguir la tendencia',
  media_prepandemia_2017_2018: 'la media antes de la pandemia',
  rmse_cerrado: 'el modelo cerrado',
  rmse_proyeccion_ine: 'la proyección oficial del INE',
  rmse_pivote_permisos: 'destinos ajustados por permisos',
  rmse_gravedad_permisos: 'gravedad con permisos',
  rmse_radiacion: 'el modelo de radiación',
}

const humano = (s: string) => s.replace(/^rmse_/, '').replace(/_/g, ' ')

/** En seguridad el modelo se prueba a dos plazos, cada uno contra las alternativas que conocen los mismos años. */
const SEGURIDAD: { id: string; titulo: string; modelo: string; rivales: string[] }[] = [
  { id: 'seguridad-2', titulo: 'Delitos: 2024 visto desde 2022', modelo: 'modelo_2_anios', rivales: ['persistencia_2022', 'tendencia_2022_2023', 'media_prepandemia_2017_2018'] },
  { id: 'seguridad-1', titulo: 'Delitos: 2024 visto desde 2023', modelo: 'modelo_1_anio', rivales: ['persistencia_2023'] },
]

export function resumirPruebas(v: Validacion): FilaPrueba[] {
  const out: FilaPrueba[] = []
  const mejor = (cands: { clave: string; valor: number }[]) => (cands.length > 0 ? cands.reduce((m, e) => (e.valor < m.valor ? e : m)) : null)
  for (const b of v.bloques) {
    const val = (k: string) => b.valores.find((x) => x.clave === k)
    if (b.id === 'seguridad') {
      for (const s of SEGURIDAD) {
        const m = val(s.modelo)
        const r = mejor(s.rivales.map(val).filter((x): x is { clave: string; valor: number } => !!x))
        if (m && r)
          out.push({ id: s.id, titulo: s.titulo, modelo: m.valor, rival: { nombre: RIVALES[r.clave] ?? humano(r.clave), valor: r.valor }, resultado: comparar(m.valor, r.valor), formato: 'pct' })
      }
      continue
    }
    const m = val('rmse_modelo')
    const r = mejor(b.valores.filter((x) => x.clave.startsWith('rmse_') && x.clave !== 'rmse_modelo'))
    if (!m || !r) continue
    out.push({
      id: b.id,
      titulo: TITULOS[b.id] ?? humano(b.id).replace(/^./, (c) => c.toUpperCase()),
      modelo: m.valor,
      rival: { nombre: RIVALES[r.clave] ?? humano(r.clave), valor: r.valor },
      resultado: comparar(m.valor, r.valor),
      formato: b.id === 'hogares' || b.unidad === 'personas' ? 'personas' : 'aire',
    })
  }
  return out
}

export function contarPruebas(filas: readonly FilaPrueba[]): Record<Resultado, number> {
  const n: Record<Resultado, number> = { gana: 0, empata: 0, pierde: 0 }
  for (const f of filas) n[f.resultado]++
  return n
}
