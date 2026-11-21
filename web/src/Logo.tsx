import { useEffect, useState } from "react";
import type { CSSProperties, Ref } from "react";

const TEXT = "root.";
const FONT = '700 100px "Figtree"';
const LETTER_SPACING = "-13px"; // must match .logo text in styles.css

type Geometry = {
  /** Ink bounds of "root." in SVG user units (font-size 100). */
  box: { left: number; top: number; width: number; height: number };
  /** The period, drawn as a circle so the globe can take its place. */
  dot: { cx: number; cy: number; r: number };
};

// Used until Figtree loads (or if measuring isn't possible).
const FALLBACK: Geometry = {
  box: { left: 7, top: -72, width: 170.5, height: 72.5 },
  dot: { cx: 170, cy: -8, r: 8 },
};

// Measures the real ink of "root." and of its period, so the viewBox hugs the
// glyphs and the circle sits exactly where the font draws the period.
async function measure(): Promise<Geometry> {
  await document.fonts.load(FONT, TEXT);
  const ctx = document.createElement("canvas").getContext("2d")!;
  ctx.font = FONT;
  ctx.letterSpacing = LETTER_SPACING;
  const all = ctx.measureText(TEXT);
  const period = ctx.measureText(".");
  const right = all.actualBoundingBoxRight;
  const width = period.actualBoundingBoxLeft + period.actualBoundingBoxRight;
  const top = -period.actualBoundingBoxAscent;
  const bottom = period.actualBoundingBoxDescent;
  return {
    box: {
      left: -all.actualBoundingBoxLeft,
      top: -all.actualBoundingBoxAscent,
      width: all.actualBoundingBoxLeft + all.actualBoundingBoxRight,
      height: all.actualBoundingBoxAscent + all.actualBoundingBoxDescent,
    },
    dot: { cx: right - width / 2, cy: (top + bottom) / 2, r: Math.max(width, bottom - top) / 2 },
  };
}

export function Logo({ ref }: { ref?: Ref<HTMLDivElement> }) {
  const [geo, setGeo] = useState<Geometry>(FALLBACK);

  useEffect(() => {
    let cancelled = false;
    measure().then((g) => {
      if (!cancelled) setGeo(g);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const { box, dot } = geo;
  const style = { "--ar": box.width / box.height } as CSSProperties;

  return (
    <div className="logo-box" ref={ref} style={style}>
      <svg
        className="logo"
        viewBox={`${box.left} ${box.top} ${box.width} ${box.height}`}
        role="img"
        aria-label={TEXT}
      >
        <text x="0" y="0" fontSize="100">
          root
        </text>
        <circle className="logo-dot" cx={dot.cx} cy={dot.cy} r={dot.r} />
      </svg>
    </div>
  );
}
