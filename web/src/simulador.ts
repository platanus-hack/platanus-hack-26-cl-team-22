/**
 * Paso de la landing al simulador con datos reales (la interfaz de viz/).
 * En el sitio publicado vive en simulador/, junto a la landing (lo copia scripts/incluir-simulador.mjs);
 * en desarrollo, VITE_SIMULADOR_URL apunta al servidor de viz/ (ver .env.development).
 */
export const URL_SIMULADOR: string = (import.meta.env.VITE_SIMULADOR_URL as string | undefined) || "simulador/";

/**
 * El vuelo del globo hasta la región dura 2,6 s (engine.js, go("region")) y recién al final dibuja
 * las comunas del simulador de ejemplo. El velo se cierra antes, mientras todavía se ve el globo.
 */
const VELO_DESDE_MS = 800;
/** Keep in sync with the .salida transition in styles.css. */
const VELO_MS = 700;

let saliendo = false;

/**
 * Deja que el globo vuele hasta Santiago y, al llegar, cubre la página con el papel del simulador
 * y navega. Con movimiento reducido navega de inmediato.
 */
export function entrarAlSimulador(): void {
  if (saliendo) return;
  saliendo = true;
  const quieto = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (quieto) {
    location.assign(URL_SIMULADOR);
    return;
  }
  document.body.classList.add("saliendo");
  window.setTimeout(() => document.body.classList.add("velo"), VELO_DESDE_MS);
  window.setTimeout(() => location.assign(URL_SIMULADOR), VELO_DESDE_MS + VELO_MS + 60);
}

// Al volver con el botón "atrás" el navegador puede restaurar la página tal como quedó: se limpia el velo.
/**
 * Al terminar el scroll la introducción queda en pantalla. Se entra con el botón o, pasado un momento
 * para alcanzar a leer, con un gesto nuevo de seguir bajando (rueda, flecha, espacio o deslizar).
 * El impulso del scroll que trajo hasta aquí no cuenta: la rueda tiene que haber estado quieta antes.
 */
const GRACIA_MS = 2500;
const PAUSA_RUEDA_MS = 450;
const TECLAS = new Set(["ArrowDown", "PageDown", " ", "Enter"]);

document.addEventListener("intro-fin", () => {
  const desde = performance.now();
  const entrar = () => {
    if (performance.now() - desde < GRACIA_MS) return;
    document.getElementById("cta")?.click();
  };
  let y0: number | null = null;
  let ultimaRueda = desde;
  window.addEventListener(
    "wheel",
    (e) => {
      // Hora del gesto, no de cuando se atiende: el dibujo del globo puede demorar al navegador.
      const ahora = e.timeStamp;
      const gestoNuevo = ahora - ultimaRueda > PAUSA_RUEDA_MS;
      ultimaRueda = ahora;
      if (gestoNuevo && e.deltaY > 0) entrar();
    },
    { passive: true },
  );
  window.addEventListener("keydown", (e) => {
    if (TECLAS.has(e.key) && !(e.target instanceof HTMLButtonElement)) entrar();
  });
  window.addEventListener("touchstart", (e) => (y0 = e.touches[0]?.clientY ?? null), { passive: true });
  window.addEventListener("touchend", (e) => {
    const y1 = e.changedTouches[0]?.clientY;
    if (y0 !== null && y1 !== undefined && y0 - y1 > 40) entrar();
    y0 = null;
  });
});

// La intro siempre parte desde el logo, así que una página restaurada tal como quedó se vuelve a cargar.
window.addEventListener("pageshow", (e) => {
  if (e.persisted) {
    location.reload();
    return;
  }
  saliendo = false;
  document.body.classList.remove("saliendo", "velo");
});
