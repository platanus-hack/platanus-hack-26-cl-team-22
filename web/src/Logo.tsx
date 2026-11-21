import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

const TEXT = "root.";
const FONT = '700 100px "Figtree"';
const LETTER_SPACING = "-13px"; // must match .logo text in styles.css

// Fallback used until the font loads (or if measuring isn't possible).
const FALLBACK = { left: 7, top: -72, width: 170.5, height: 72.5 };

type Box = typeof FALLBACK;

// Measures the real ink bounds of the text, so the viewBox hugs the glyphs.
async function measureInk(): Promise<Box> {
  await document.fonts.load(FONT, TEXT);
  const ctx = document.createElement("canvas").getContext("2d")!;
  ctx.font = FONT;
  ctx.letterSpacing = LETTER_SPACING;
  const m = ctx.measureText(TEXT);
  return {
    left: -m.actualBoundingBoxLeft,
    top: -m.actualBoundingBoxAscent,
    width: m.actualBoundingBoxLeft + m.actualBoundingBoxRight,
    height: m.actualBoundingBoxAscent + m.actualBoundingBoxDescent,
  };
}

export function Logo() {
  const [box, setBox] = useState<Box>(FALLBACK);

  useEffect(() => {
    let cancelled = false;
    measureInk().then((b) => {
      if (!cancelled) setBox(b);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const style = { "--ar": box.width / box.height } as CSSProperties;

  return (
    <svg
      className="logo"
      style={style}
      viewBox={`${box.left} ${box.top} ${box.width} ${box.height}`}
      role="img"
      aria-label={TEXT}
    >
      <text x="0" y="0" fontSize="100">
        {TEXT}
      </text>
    </svg>
  );
}
