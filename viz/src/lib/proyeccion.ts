import type { Limites } from './vista'

/** Punto en coordenadas de mundo: x = lon · cos(lat0), y = −lat (el norte queda arriba en pantalla). */
export type Pt = [number, number]
/** Polígono: anillo exterior y huecos. */
export type Poligono = Pt[][]

export type Proyectar = (lon: number, lat: number) => Pt

/** Equirrectangular corregida por el coseno de la latitud central de los límites. */
export function crearProyeccion(lim: Limites): Proyectar {
  const lat0 = (lim[1] + lim[3]) / 2
  const c = Math.cos((lat0 * Math.PI) / 180)
  return (lon, lat) => [lon * c, -lat]
}

const esPar = (v: unknown): v is [number, number] =>
  Array.isArray(v) && typeof v[0] === 'number' && typeof v[1] === 'number' && Number.isFinite(v[0]) && Number.isFinite(v[1])

function anillo(raw: unknown, proj: Proyectar): Pt[] | null {
  if (!Array.isArray(raw)) return null
  const out: Pt[] = []
  for (const p of raw) if (esPar(p)) out.push(proj(p[0], p[1]))
  return out.length >= 3 ? out : null
}

function poligono(raw: unknown, proj: Proyectar): Poligono | null {
  if (!Array.isArray(raw)) return null
  const rings = raw.map((r) => anillo(r, proj)).filter((r): r is Pt[] => r !== null)
  return rings.length > 0 ? rings : null
}

/** Polígonos proyectados de una geometría GeoJSON (Polygon o MultiPolygon). Lo mal formado se descarta. */
export function proyectarGeometria(geom: { type: string; coordinates: unknown }, proj: Proyectar): Poligono[] {
  if (geom.type === 'Polygon') {
    const p = poligono(geom.coordinates, proj)
    return p ? [p] : []
  }
  if (geom.type === 'MultiPolygon' && Array.isArray(geom.coordinates)) {
    return geom.coordinates.map((c) => poligono(c, proj)).filter((p): p is Poligono => p !== null)
  }
  return []
}

const f = (n: number) => n.toFixed(5)

/** Ruta SVG de anillos cerrados. */
export function rutaDeAnillos(anillos: readonly Pt[][]): string {
  return anillos.map((r) => 'M' + r.map((p) => `${f(p[0])},${f(p[1])}`).join('L') + 'Z').join('')
}

export function rutaDePoligonos(ps: readonly Poligono[]): string {
  return ps.map((p) => rutaDeAnillos(p)).join('')
}

/** Área con signo (fórmula del cordón). Positiva = sentido horario en pantalla (y hacia abajo). */
export function areaAnillo(r: readonly Pt[]): number {
  let s = 0
  for (let i = 0; i < r.length; i++) {
    const a = r[i]!
    const b = r[(i + 1) % r.length]!
    s += a[0] * b[1] - b[0] * a[1]
  }
  return s / 2
}

export function centroideAnillo(r: readonly Pt[]): Pt {
  let cx = 0
  let cy = 0
  let a2 = 0
  for (let i = 0; i < r.length; i++) {
    const a = r[i]!
    const b = r[(i + 1) % r.length]!
    const cr = a[0] * b[1] - b[0] * a[1]
    a2 += cr
    cx += (a[0] + b[0]) * cr
    cy += (a[1] + b[1]) * cr
  }
  if (Math.abs(a2) < 1e-15) {
    const n = r.length || 1
    return [r.reduce((s, p) => s + p[0], 0) / n, r.reduce((s, p) => s + p[1], 0) / n]
  }
  return [cx / (3 * a2), cy / (3 * a2)]
}

/** Punto dentro de un anillo (regla par-impar). */
export function dentroAnillo(p: Pt, r: readonly Pt[]): boolean {
  let dentro = false
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const a = r[i]!
    const b = r[j]!
    if (a[1] > p[1] !== b[1] > p[1] && p[0] < ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0]) dentro = !dentro
  }
  return dentro
}

export function dentroPoligono(p: Pt, pol: Poligono): boolean {
  const [ext, ...huecos] = pol
  if (!ext || !dentroAnillo(p, ext)) return false
  return !huecos.some((h) => dentroAnillo(p, h))
}

/** El polígono de mayor área (la parte principal de una comuna con islas). */
export function poligonoMayor(ps: readonly Poligono[]): Poligono | null {
  let mejor: Poligono | null = null
  let am = -1
  for (const p of ps) {
    const a = Math.abs(areaAnillo(p[0]!))
    if (a > am) {
      am = a
      mejor = p
    }
  }
  return mejor
}

/**
 * Un punto que cae dentro del polígono: el centroide si está dentro; si no, el medio del tramo
 * horizontal más ancho que cruza la altura del centroide.
 */
export function puntoInterior(pol: Poligono): Pt {
  const ext = pol[0]!
  const c = centroideAnillo(ext)
  if (dentroPoligono(c, pol)) return c
  const y = c[1]
  const xs: number[] = []
  for (const r of pol) {
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const a = r[i]!
      const b = r[j]!
      if (a[1] > y !== b[1] > y) xs.push(a[0] + ((y - a[1]) * (b[0] - a[0])) / (b[1] - a[1]))
    }
  }
  xs.sort((m, n) => m - n)
  let mejor: Pt = c
  let ancho = -1
  for (let i = 0; i + 1 < xs.length; i += 2) {
    const w = xs[i + 1]! - xs[i]!
    if (w > ancho) {
      ancho = w
      mejor = [(xs[i]! + xs[i + 1]!) / 2, y]
    }
  }
  return mejor
}

export interface Caja {
  x0: number
  y0: number
  x1: number
  y1: number
}

export function cajaDePoligonos(ps: readonly Poligono[]): Caja | null {
  const c: Caja = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity }
  for (const p of ps)
    for (const r of p)
      for (const q of r) {
        c.x0 = Math.min(c.x0, q[0])
        c.y0 = Math.min(c.y0, q[1])
        c.x1 = Math.max(c.x1, q[0])
        c.y1 = Math.max(c.y1, q[1])
      }
  return Number.isFinite(c.x0) ? c : null
}

/** Transformación de mundo a pantalla: pantalla = mundo · k + t. */
export interface Vista {
  k: number
  tx: number
  ty: number
}

export interface Margen {
  izq: number
  der: number
  sup: number
  inf: number
}

/** Vista que hace caber la caja en el rectángulo libre (ancho × alto menos márgenes), centrada en él. */
export function ajustarCaja(c: Caja, ancho: number, alto: number, m: Margen): Vista {
  const lw = Math.max(40, ancho - m.izq - m.der)
  const lh = Math.max(40, alto - m.sup - m.inf)
  const dx = Math.max(1e-9, c.x1 - c.x0)
  const dy = Math.max(1e-9, c.y1 - c.y0)
  const k = Math.min(lw / dx, lh / dy)
  const cx = (c.x0 + c.x1) / 2
  const cy = (c.y0 + c.y1) / 2
  return { k, tx: m.izq + lw / 2 - cx * k, ty: m.sup + lh / 2 - cy * k }
}

/** Interpola dos vistas por el centro de pantalla en coordenadas de mundo y el logaritmo del zoom. */
export function interpolarVista(a: Vista, b: Vista, t: number, ancho: number, alto: number): Vista {
  const sx = ancho / 2
  const sy = alto / 2
  const ca: Pt = [(sx - a.tx) / a.k, (sy - a.ty) / a.k]
  const cb: Pt = [(sx - b.tx) / b.k, (sy - b.ty) / b.k]
  const k = Math.exp(Math.log(a.k) + (Math.log(b.k) - Math.log(a.k)) * t)
  const cx = ca[0] + (cb[0] - ca[0]) * t
  const cy = ca[1] + (cb[1] - ca[1]) * t
  return { k, tx: sx - cx * k, ty: sy - cy * k }
}

/** Zoom por un factor dejando fijo el punto de pantalla (px, py). */
export function zoomEn(v: Vista, factor: number, px: number, py: number): Vista {
  const k = v.k * factor
  return { k, tx: px - (px - v.tx) * factor, ty: py - (py - v.ty) * factor }
}

/**
 * Mantiene el zoom entre topes y no deja que la caja de la región salga del todo de la pantalla:
 * al menos `borde` píxeles de la región quedan siempre a la vista en cada eje.
 */
export function limitarVista(v: Vista, c: Caja, ancho: number, alto: number, kMin: number, kMax: number, borde = 80): Vista {
  let r = v
  const k = Math.min(kMax, Math.max(kMin, v.k))
  if (k !== v.k) r = zoomEn(v, k / v.k, ancho / 2, alto / 2)
  const x0 = c.x0 * r.k + r.tx
  const x1 = c.x1 * r.k + r.tx
  const y0 = c.y0 * r.k + r.ty
  const y1 = c.y1 * r.k + r.ty
  let tx = r.tx
  let ty = r.ty
  if (x1 < borde) tx += borde - x1
  if (x0 > ancho - borde) tx -= x0 - (ancho - borde)
  if (y1 < borde) ty += borde - y1
  if (y0 > alto - borde) ty -= y0 - (alto - borde)
  return { k: r.k, tx, ty }
}

/** Curva cuadrática de a hasta b, combada hacia un lado en una fracción del largo. */
export function rutaCurva(a: Pt, b: Pt, comba = 0.22): string {
  const mx = (a[0] + b[0]) / 2
  const my = (a[1] + b[1]) / 2
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const cx = mx - dy * comba
  const cy = my + dx * comba
  return `M${f(a[0])},${f(a[1])}Q${f(cx)},${f(cy)} ${f(b[0])},${f(b[1])}`
}
