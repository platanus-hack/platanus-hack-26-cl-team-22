import type { SimulatorApi } from "./simulator/engine";
import { createRoots } from "./roots";

// Landing colors (keep in sync with --bg / --dot in styles.css).
const BG = "#092122";
const DOT = "#6b3f20";

// The globe starts as a flat disc of the dot's color (every layer painted the
// same, so it reads as a plain circle), then fades into the simulator's own
// palette as the zoom goes in, revealing the world.
const TINT = { ocean: DOT, land: DOT, border: DOT, grat: DOT, accent: DOT };

type Elements = {
  spacer: HTMLElement;
  layer: HTMLElement;
  box: HTMLElement;
  /** Full-screen canvas behind the logo where the roots grow. */
  roots: HTMLCanvasElement;
  sim: { api: SimulatorApi; root: HTMLElement } | null;
};

const clamp01 = (t: number) => Math.min(1, Math.max(0, t));
const smooth = (a: number, b: number, x: number) => {
  const t = clamp01((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

function mixHex(from: string, to: string, t: number) {
  const parse = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const a = parse(from);
  const b = parse(to);
  return `rgb(${a.map((v, i) => Math.round(lerp(v, b[i], t))).join(",")})`;
}

// Same placement the simulator uses for its "Mundo" view (engine.js world()).
function fallbackWorld(w: number, h: number) {
  const wide = w > 860;
  return { x: wide ? w * 0.62 : w * 0.5, y: wide ? h * 0.5 : h * 0.27, r: Math.min(w, h) * (wide ? 0.4 : 0.36) };
}

export type IntroHandle = {
  /** Stops listening (React effect cleanup). */
  dispose(): void;
  /** From the simulator back to the logo: plays the intro in reverse. */
  reopen(): Promise<void>;
};

// Any of these cancels the automatic scroll back to the logo.
const USER_INPUT = ["wheel", "touchstart", "pointerdown", "keydown"] as const;
const REVERSE_MS = 1800;
const GLOBE_FADE_MS = 600; // keep in sync with .sim #map transition in simulator.css

/**
 * Scroll-driven intro: the period of "root." is the globe. Scrolling down
 * zooms into it (letters grow and fade), centers it, and hands over to the
 * simulator's world view. Reaching the end commits: the scroll spacer and the
 * logo go away and the simulator takes the page. reopen() undoes the commit.
 */
export function startIntro({ spacer, layer, box, roots: rootsCanvas, sim }: Elements): IntroHandle {
  const html = document.documentElement;
  const svg = box.querySelector("svg")!;
  const dot = box.querySelector<SVGCircleElement>(".logo-dot")!;
  const pageColor = getComputedStyle(html).getPropertyValue("--page").trim() || "#E8EFEE";
  const roots = createRoots(rootsCanvas, { root: DOT, crumbs: [DOT, "#8a5a33", "#3d2614"] });
  let raf = 0;
  let autoRaf = 0;
  // Read from the page, not assumed: if this controller is re-created after the
  // simulator already took over (React re-running the effect, e.g. on a hot
  // reload in development), it must stay idle instead of resetting the globe
  // to the size of the period.
  let committed = document.body.classList.contains("sim-on");
  // After reopen() the page starts at the very bottom; don't commit again
  // until the user has actually moved away from it.
  let armed = true;
  let returning = false;

  function update() {
    raf = 0;
    const W = innerWidth;
    const H = innerHeight;
    const max = html.scrollHeight - H;
    const p = max > 0 ? clamp01(scrollY / max) : 0;

    // Where the period is right now (untransformed layout of the logo).
    const rect = box.getBoundingClientRect();
    const vb = svg.viewBox.baseVal;
    const k = rect.width / vb.width;
    const D = {
      x: rect.left + (dot.cx.baseVal.value - vb.x) * k,
      y: rect.top + (dot.cy.baseVal.value - vb.y) * k,
      r: dot.r.baseVal.value * k,
    };
    const world = sim ? sim.api.world() : fallbackWorld(W, H);

    // a: zoom into the period and bring it to the middle of the screen.
    // b: slide to the simulator's world position while its UI fades in.
    const a = ease(smooth(0, 0.8, p));
    const b = ease(smooth(0.75, 1, p));
    const s = Math.exp(Math.log(world.r / D.r) * a);
    const x = lerp(lerp(D.x, W / 2, a), world.x, b);
    const y = lerp(lerp(D.y, H / 2, a), world.y, b);

    // Letters zoom with the same camera, anchored on the period.
    svg.style.transform = `translate(${x - rect.left + s * (rect.left - D.x)}px, ${
      y - rect.top + s * (rect.top - D.y)
    }px) scale(${s})`;
    svg.style.opacity = String(1 - smooth(0.2, 0.65, p));

    // The disc dissolves into the world in step with the zoom (a), not the raw
    // scroll, so it stays a plain circle at the start and is revealed as we go in.
    const mix = smooth(0.1, 0.9, a);
    document.body.style.background = mixHex(BG, pageColor, mix);

    // Roots spread from the period's edge to the whole screen while the zoom
    // goes in, then fade before the simulator's UI takes over.
    roots.draw({ x, y, r: D.r * s, grow: ease(smooth(0.02, 0.6, p)), alpha: 1 - smooth(0.6, 0.85, p) });

    if (sim) {
      revealGlobe(sim.root);
      sim.root.style.setProperty("--ui", String(b));
      sim.api.setIntro({ x, y, r: D.r * s, mix, ui: b, tint: TINT });
      if (p < 0.95) armed = true;
      if (armed && p >= 0.999) commit();
    }
  }

  // First time the globe is drawn it fades in over the ink period (continents
  // "emerge" from the dot); the placeholder goes away once it's covered.
  function revealGlobe(root: HTMLElement) {
    if (root.classList.contains("globe-in")) return;
    root.classList.add("globe-in");
    setTimeout(() => (dot.style.opacity = "0"), GLOBE_FADE_MS);
  }

  function commit() {
    stopAutoScroll();
    unlisten();
    committed = true;
    html.classList.remove("intro-on");
    spacer.style.display = "none";
    layer.style.display = "none";
    document.body.style.background = "";
    document.body.classList.add("sim-on");
    sim!.root.classList.remove("is-intro");
    sim!.root.style.removeProperty("--ui");
    sim!.api.setIntro(null);
    roots.clear();
    setHomeDisabled(false);
    scrollTo(0, 0);
  }

  async function reopen() {
    if (!sim || !committed || returning) return;
    const { root, api } = sim;
    // One click only: the button stays disabled (also for keyboard, which
    // pointer-events doesn't block) until the simulator is entered again.
    returning = true;
    setHomeDisabled(true);
    // Fly the globe back to the starting world view first (no input meanwhile).
    root.style.pointerEvents = "none";
    scrollTo(0, 0);
    await api.goHome();
    root.style.pointerEvents = "";

    // Undo the commit, landing exactly at the end of the intro (same frame
    // the simulator was showing), then scroll back up to the logo.
    committed = false;
    armed = false;
    document.body.classList.remove("sim-on");
    root.classList.add("is-intro");
    spacer.style.display = "";
    layer.style.display = "";
    listen();
    scrollTo(0, html.scrollHeight - innerHeight);
    update();
    returning = false;
    autoScrollToTop();
  }

  function setHomeDisabled(disabled: boolean) {
    const home = sim?.root.querySelector<HTMLButtonElement>(".brand .home");
    if (!home) return;
    home.disabled = disabled;
    if (disabled) home.blur();
  }

  function autoScrollToTop() {
    const y0 = scrollY;
    const t0 = performance.now();
    USER_INPUT.forEach((type) => addEventListener(type, stopAutoScroll, { passive: true }));
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / REVERSE_MS);
      scrollTo(0, y0 * (1 - ease(t)));
      if (t < 1) autoRaf = requestAnimationFrame(step);
      else stopAutoScroll();
    };
    autoRaf = requestAnimationFrame(step);
  }

  function stopAutoScroll() {
    cancelAnimationFrame(autoRaf);
    autoRaf = 0;
    USER_INPUT.forEach((type) => removeEventListener(type, stopAutoScroll));
  }

  const schedule = () => {
    if (!raf) raf = requestAnimationFrame(update);
  };
  const resizeObserver = new ResizeObserver(schedule);
  const mutationObserver = new MutationObserver(schedule);

  function listen() {
    html.classList.add("intro-on");
    addEventListener("scroll", schedule, { passive: true });
    addEventListener("resize", schedule);
    resizeObserver.observe(box);
    // Logo geometry changes once Figtree is measured (not on our own style writes).
    mutationObserver.observe(svg, { attributes: true, subtree: true, attributeFilter: ["viewBox", "cx", "cy", "r"] });
  }

  function unlisten() {
    cancelAnimationFrame(raf);
    raf = 0;
    removeEventListener("scroll", schedule);
    removeEventListener("resize", schedule);
    resizeObserver.disconnect();
    mutationObserver.disconnect();
  }

  if (!committed) {
    listen();
    update();
  }

  return {
    dispose() {
      stopAutoScroll();
      unlisten();
    },
    reopen,
  };
}
