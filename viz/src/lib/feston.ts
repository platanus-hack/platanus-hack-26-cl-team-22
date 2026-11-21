import { areaAnillo, type Pt } from './proyeccion'

/** Quita vértices más cercanos que `minimo` al último conservado (los festones necesitan tramos largos). */
export function diezmar(r: readonly Pt[], minimo: number): Pt[] {
  if (r.length === 0) return []
  const out: Pt[] = [r[0]!]
  for (let i = 1; i < r.length; i++) {
    const p = r[i]!
    const u = out[out.length - 1]!
    if (Math.hypot(p[0] - u[0], p[1] - u[1]) >= minimo) out.push(p)
  }
  // el último no debe pegarse al primero
  while (out.length > 3) {
    const a = out[out.length - 1]!
    if (Math.hypot(a[0] - out[0]![0], a[1] - out[0]![1]) >= minimo) break
    out.pop()
  }
  return out
}

export function escalarAnillo(r: readonly Pt[], centro: Pt, s: number): Pt[] {
  return r.map((p) => [centro[0] + (p[0] - centro[0]) * s, centro[1] + (p[1] - centro[1]) * s])
}

export function anilloCircular(cx: number, cy: number, radio: number, lados: number): Pt[] {
  return Array.from({ length: lados }, (_, i) => {
    const a = (i / lados) * 2 * Math.PI - Math.PI / 2
    return [cx + radio * Math.cos(a), cy + radio * Math.sin(a)] as Pt
  })
}

const f = (n: number) => n.toFixed(5)

/**
 * Borde festoneado (de tijera dentada): cada tramo del anillo se reparte en arcos de largo cercano
 * a `paso`, todos combados hacia afuera. `curva` es el radio del arco sobre la cuerda (≥ 0,5).
 */
export function rutaFestoneada(anilloEntrada: readonly Pt[], paso: number, curva = 0.62): string {
  const r = diezmar(anilloEntrada, paso * 0.8)
  if (r.length < 3) return ''
  const barrido = areaAnillo(r) > 0 ? 1 : 0
  let d = `M${f(r[0]![0])},${f(r[0]![1])}`
  for (let i = 0; i < r.length; i++) {
    const a = r[i]!
    const b = r[(i + 1) % r.length]!
    const largo = Math.hypot(b[0] - a[0], b[1] - a[1])
    const n = Math.max(1, Math.round(largo / paso))
    const rr = (largo / n) * Math.max(0.5, curva)
    for (let j = 1; j <= n; j++) {
      const x = a[0] + ((b[0] - a[0]) * j) / n
      const y = a[1] + ((b[1] - a[1]) * j) / n
      d += `A${f(rr)},${f(rr)} 0 0 ${barrido} ${f(x)},${f(y)}`
    }
  }
  return d + 'Z'
}

/** Rodela festoneada: círculo de `n` festones. */
export function rutaRodela(cx: number, cy: number, radio: number, n: number): string {
  const lados = n
  const cuerda = 2 * radio * Math.sin(Math.PI / lados)
  return rutaFestoneada(anilloCircular(cx, cy, radio, lados), cuerda, 0.56)
}
