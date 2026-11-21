/**
 * Seeded pseudo-random numbers for the simulations (never Math.random, so runs are reproducible).
 *
 * Generator: mulberry32 (32-bit state, period 2^32), plenty for ~10^6 draws per run.
 * Poisson: Knuth's multiplication method for small lambda and Hörmann's PTRS (transformed
 * rejection with squeeze, exact) for lambda ≥ 30.
 */

export interface Prng {
  /** Uniform in [0, 1). */
  uniform(): number
  /** Poisson(lambda) draw; 0 when lambda ≤ 0. */
  poisson(lambda: number): number
  /** Fisher–Yates shuffle in place. */
  barajar(xs: { length: number; [i: number]: number }): void
  /** Index drawn with probability proportional to `pesos[i]`; −1 when every weight is 0. */
  categorica(pesos: ArrayLike<number>): number
}

/** Log of Gamma(x) for x > 0 (Lanczos, g = 7, ~15 digits). */
function logGamma(x: number): number {
  const c = [
    0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059,
    12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
  ]
  if (x < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * x)) - logGamma(1 - x)
  x -= 1
  let a = c[0]!
  const t = x + 7.5
  for (let i = 1; i < 9; i++) a += c[i]! / (x + i)
  return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a)
}

export function crearPrng(semilla: number): Prng {
  let estado = semilla >>> 0

  const uniform = () => {
    estado = (estado + 0x6d2b79f5) >>> 0
    let z = estado
    z = Math.imul(z ^ (z >>> 15), z | 1)
    z ^= z + Math.imul(z ^ (z >>> 7), z | 61)
    return ((z ^ (z >>> 14)) >>> 0) / 4294967296
  }

  const poissonKnuth = (lambda: number) => {
    const limite = Math.exp(-lambda)
    let k = 0
    let p = uniform()
    while (p > limite) {
      k++
      p *= uniform()
    }
    return k
  }

  const poissonPtrs = (lambda: number) => {
    const slam = Math.sqrt(lambda)
    const loglam = Math.log(lambda)
    const b = 0.931 + 2.53 * slam
    const a = -0.059 + 0.02483 * b
    const invalpha = 1.1239 + 1.1328 / (b - 3.4)
    const vr = 0.9277 - 3.6224 / (b - 2)
    for (;;) {
      const u = uniform() - 0.5
      const v = uniform()
      const us = 0.5 - Math.abs(u)
      const k = Math.floor(((2 * a) / us + b) * u + lambda + 0.43)
      if (us >= 0.07 && v <= vr) return k
      if (k < 0 || (us < 0.013 && v > us)) continue
      if (Math.log(v) + Math.log(invalpha) - Math.log(a / (us * us) + b) <= -lambda + k * loglam - logGamma(k + 1)) return k
    }
  }

  return {
    uniform,
    poisson: (lambda) => (lambda <= 0 ? 0 : lambda < 30 ? poissonKnuth(lambda) : poissonPtrs(lambda)),
    barajar(xs) {
      for (let i = xs.length - 1; i > 0; i--) {
        const j = Math.floor(uniform() * (i + 1))
        const tmp = xs[i]!
        xs[i] = xs[j]!
        xs[j] = tmp
      }
    },
    categorica(pesos) {
      let total = 0
      for (let i = 0; i < pesos.length; i++) total += pesos[i]!
      if (!(total > 0)) return -1
      let u = uniform() * total
      let ultimo = -1
      for (let i = 0; i < pesos.length; i++) {
        const w = pesos[i]!
        if (w <= 0) continue
        ultimo = i
        u -= w
        if (u < 0) return i
      }
      return ultimo
    },
  }
}
