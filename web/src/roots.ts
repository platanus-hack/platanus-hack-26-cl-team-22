/**
 * Procedural roots that grow out of the logo's period while the intro zooms
 * in, knocking crumbs loose as they pass. The shape is generated once from a fixed seed, so scrolling back and
 * forth grows and retracts the very same roots instead of re-rolling them.
 *
 * Geometry lives in normalized units (1 = screen diagonal) around the
 * period's center; draw() maps it to pixels for the current frame and pushes
 * every point outwards by the globe's radius, so the roots always start at
 * the edge of the disc however big it is.
 */

type Point = { x: number; y: number; d: number };
type Branch = { pts: Point[]; width: number };
/** Fragment knocked loose where a root passes; flies out and falls with gravity. */
type Crumb = {
  x: number;
  y: number;
  d: number;
  vx: number;
  vy: number;
  size: number;
  rot: number;
  spin: number;
  shape: number[]; // radius factor per vertex
  tone: number; // index into the crumb colors
};

const SEED = 22;
const MAIN_ROOTS = 9;
const STEP = 0.012; // segment length, in screen diagonals
const MAX_DEPTH = 3;
const BASE_WIDTH = 13; // px, at the root's base on a ~1600px-diagonal screen

// Small deterministic PRNG (mulberry32).
function prng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function generate(): { branches: Branch[]; maxD: number } {
  const rand = prng(SEED);
  const branches: Branch[] = [];
  let maxD = 0;

  function grow(x: number, y: number, angle: number, width: number, d: number, depth: number) {
    const pts: Point[] = [{ x, y, d }];
    // Main roots run past the screen edge; side roots are shorter.
    const length = depth === 0 ? 0.9 + rand() * 0.2 : (0.18 + rand() * 0.3) / depth;
    const steps = Math.max(2, Math.round(length / STEP));
    let bend = (rand() - 0.5) * 0.1;
    for (let i = 0; i < steps; i++) {
      // Wandering heading: a damped random walk gives the snake-like curls.
      bend = bend * 0.88 + (rand() - 0.5) * 0.09;
      angle += bend;
      x += Math.cos(angle) * STEP;
      y += Math.sin(angle) * STEP;
      d += STEP;
      pts.push({ x, y, d });
      const along = i / steps;
      if (depth < MAX_DEPTH && i > 2 && rand() < 0.06 * (1 - along * 0.5)) {
        const side = rand() < 0.5 ? -1 : 1;
        // Side roots keep a random share of the parent's width, so thicknesses vary.
        grow(x, y, angle + side * (0.35 + rand() * 0.7), width * (0.35 + rand() * 0.45) * (1 - along * 0.6), d, depth + 1);
      }
    }
    maxD = Math.max(maxD, d);
    branches.push({ pts, width });
  }

  for (let k = 0; k < MAIN_ROOTS; k++) {
    const angle = (k / MAIN_ROOTS) * Math.PI * 2 + (rand() - 0.5) * 0.5;
    // Mix of thick trunks and thinner main roots.
    grow(0, 0, angle, 0.45 + rand() * 1.1, 0, 0);
  }
  return { branches, maxD };
}

// Crumbs use their own random stream, so tuning them never changes the shape
// of the roots themselves.
function generateCrumbs(branches: Branch[]): Crumb[] {
  const rand = prng(SEED + 1);
  const crumbs: Crumb[] = [];
  for (const { pts, width } of branches) {
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1];
      const b = pts[i];
      const heading = Math.atan2(b.y - a.y, b.x - a.x);

      // Many more crumbs; thin roots shed a few too.
      if (rand() < 0.05 + 0.3 * width) {
        const side = rand() < 0.5 ? -1 : 1;
        const angle = heading + side * (Math.PI / 2) + (rand() - 0.5) * 1.4;
        const speed = 0.015 + rand() * 0.05;
        const vertices = 3 + Math.floor(rand() * 3);
        crumbs.push({
          x: b.x,
          y: b.y,
          d: b.d,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed - 0.015, // a small upward kick before falling
          // Skewed sizes: mostly grains, some chunky pieces.
          size: 1 + 10 * rand() ** 2.5 * Math.min(1.4, 0.5 + width),
          rot: rand() * Math.PI * 2,
          spin: (rand() - 0.5) * 40,
          shape: Array.from({ length: vertices }, () => 0.6 + rand() * 0.5),
          tone: Math.floor(rand() * 3),
        });
      }
    }
  }
  return crumbs;
}

const CRUMB_LIFE = 0.75; // distance (diagonals) a crumb lives after it breaks off
const GRAVITY = 0.35;

export type RootsColors = {
  root: string;
  /** Three tones picked at random per crumb. */
  crumbs: [string, string, string];
};

export type RootsFrame = {
  /** Center of the period / globe, in CSS pixels. */
  x: number;
  y: number;
  /** Current radius of the period / globe, in CSS pixels. */
  r: number;
  /** 0 = nothing drawn, 1 = fully grown. */
  grow: number;
  /** Overall opacity. */
  alpha: number;
};

export type Roots = { draw(frame: RootsFrame): void; clear(): void };

export function createRoots(canvas: HTMLCanvasElement, colors: RootsColors): Roots {
  const ctx = canvas.getContext("2d")!;
  const { branches, maxD } = generate();
  const crumbs = generateCrumbs(branches);
  let W = 0;
  let H = 0;

  function fit() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (w === W && h === H) return;
    W = w;
    H = h;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function clear() {
    ctx.clearRect(0, 0, W, H);
  }

  function draw({ x, y, r, grow, alpha }: RootsFrame) {
    fit();
    clear();
    if (grow <= 0 || alpha <= 0) return;
    const R = Math.hypot(W, H);
    const reach = grow * maxD;
    const scale = R / 1600;
    const px = (p: Point) => {
      const len = Math.hypot(p.x, p.y) || 1;
      const push = r / len; // start at the disc's edge, not its center
      return [x + p.x * R + p.x * push, y + p.y * R + p.y * push];
    };

    ctx.globalAlpha = alpha;
    ctx.strokeStyle = colors.root;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    for (const { pts, width } of branches) {
      if (pts[0].d >= reach) continue;
      const last = pts.length - 1;
      let [ax, ay] = px(pts[0]);
      for (let i = 1; i <= last; i++) {
        const p = pts[i];
        const prev = pts[i - 1];
        let [bx, by] = px(p);
        let done = false;
        if (p.d > reach) {
          // Partial tip segment, so growth is smooth rather than step by step.
          const t = (reach - prev.d) / (p.d - prev.d);
          bx = ax + (bx - ax) * t;
          by = ay + (by - ay) * t;
          done = true;
        }
        // Taper along the branch and towards the growing tip.
        const taper = 1 - (i / last) * 0.65;
        const tip = Math.min(1, (reach - p.d) / 0.05 + 0.35);
        ctx.lineWidth = Math.max(0.8, BASE_WIDTH * scale * width * taper * Math.max(0.35, tip));
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
        if (done) break;
        ax = bx;
        ay = by;
      }
    }

    // Crumbs on top: born when the root reaches them, then fly and fall.
    for (const c of crumbs) {
      const age = reach - c.d;
      if (age <= 0 || age >= CRUMB_LIFE) continue;
      const [bx, by] = px(c);
      const cx = bx + c.vx * age * R;
      const cy = by + (c.vy * age + 0.5 * GRAVITY * age * age) * R;
      const size = c.size * scale;
      const rot = c.rot + c.spin * age;
      // Fully visible for most of the fall, fading only at the end.
      ctx.globalAlpha = alpha * Math.min(1, (1 - age / CRUMB_LIFE) / 0.35);
      ctx.fillStyle = colors.crumbs[c.tone];
      ctx.beginPath();
      c.shape.forEach((k, i) => {
        const a = rot + (i / c.shape.length) * Math.PI * 2;
        const vx = cx + Math.cos(a) * size * k;
        const vy = cy + Math.sin(a) * size * k;
        if (i === 0) ctx.moveTo(vx, vy);
        else ctx.lineTo(vx, vy);
      });
      ctx.closePath();
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  return { draw, clear };
}
