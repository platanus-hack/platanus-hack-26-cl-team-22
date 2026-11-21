/**
 * Paso de la landing al simulador con datos reales (la interfaz de viz/).
 * En el sitio publicado vive en simulador/, junto a la landing (lo copia scripts/incluir-simulador.mjs);
 * en desarrollo, VITE_SIMULADOR_URL apunta al servidor de viz/ (ver .env.development).
 */
export const URL_SIMULADOR: string = (import.meta.env.VITE_SIMULADOR_URL as string | undefined) || "simulador/";

/** Lo que tarda el vuelo del globo hasta la Región Metropolitana (engine.js, go("region")). */
const VUELO_MS = 2600;
/** Keep in sync with the .salida transition in styles.css. */
const VELO_MS = 700;

let saliendo = false;

/**
 * Deja que el globo vuele hasta Santiago y, al llegar, cubre la página con el papel del simulador
 * y navega. Con movimiento reducido navega de inmediato. La intro lo dispara sola al terminar el scroll.
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
  window.setTimeout(() => document.body.classList.add("velo"), VUELO_MS - VELO_MS);
  window.setTimeout(() => location.assign(URL_SIMULADOR), VUELO_MS + 80);
}

// Al volver con el botón "atrás" el navegador puede restaurar la página tal como quedó: se limpia el velo.
// La intro siempre parte desde el logo, así que una página restaurada tal como quedó se vuelve a cargar.
window.addEventListener("pageshow", (e) => {
  if (e.persisted) {
    location.reload();
    return;
  }
  saliendo = false;
  document.body.classList.remove("saliendo", "velo");
});
