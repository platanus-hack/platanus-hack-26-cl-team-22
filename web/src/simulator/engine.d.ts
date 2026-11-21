export type IntroCam = {
  /** Centro del globo en pantalla (px). */
  x: number;
  y: number;
  /** Radio del globo (px). */
  r: number;
  /** 0 = colores del logo (tint), 1 = colores del simulador. */
  mix: number;
  /** Opacidad del marcador de Santiago (0 a 1). */
  ui: number;
  tint: Partial<Record<"ocean" | "land" | "border" | "grat" | "accent", string>>;
};

export type SimulatorApi = {
  /** Fija la cámara de la intro; null devuelve el control al simulador. */
  setIntro(cam: IntroCam | null): void;
  /** Vuelve a la vista "Mundo" de partida; resuelve al terminar el vuelo. */
  goHome(): Promise<void>;
  /** Dónde dibuja el simulador el globo en su vista "Mundo". */
  world(): { x: number; y: number; r: number };
};

export type MountOptions = {
  /** No dibuja nada hasta el primer setIntro() (evita un cuadro con el globo grande al cargar). */
  startHidden?: boolean;
};

export function mountSimulator(root: HTMLElement, opts?: MountOptions): SimulatorApi;
