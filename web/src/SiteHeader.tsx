import { useEffect, useState } from "react";

// Keys that scroll the page up or down.
const UP_KEYS = ["ArrowUp", "PageUp", "Home"];
const DOWN_KEYS = ["ArrowDown", "PageDown", "End", " "];

const TEAM = [
  { name: "Jesús Gil", github: "Jrgil20" },
  { name: "Gabriel Castellano", github: "GdCastellano" },
  { name: "Daniel Bruno", github: "Holeekey" },
  { name: "Valeria Riera", github: "ingvaleriariera" },
  { name: "Massiel Perozo", github: "massiperozo" },
];

/**
 * Header with what the project is and who built it. Hidden by default: it
 * slides in only when the user tries to scroll up past the top of the logo
 * page, and goes away again with any downward scroll. It never shows once the
 * simulator has taken over (body.sim-on, see styles.css).
 */
export function SiteHeader() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const atTop = () => scrollY <= 0;
    let touchY = 0;

    const onWheel = (e: WheelEvent) => {
      if (e.deltaY < 0 && atTop()) setVisible(true);
      else if (e.deltaY > 0) setVisible(false);
    };
    const onTouchStart = (e: TouchEvent) => {
      touchY = e.touches[0].clientY;
    };
    const onTouchMove = (e: TouchEvent) => {
      const dy = e.touches[0].clientY - touchY;
      // Finger moving down means the page is being pulled up.
      if (dy > 12 && atTop()) setVisible(true);
      else if (dy < -12) setVisible(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (UP_KEYS.includes(e.key) && atTop()) setVisible(true);
      else if (DOWN_KEYS.includes(e.key)) setVisible(false);
    };
    const onScroll = () => {
      if (!atTop()) setVisible(false);
    };

    addEventListener("wheel", onWheel, { passive: true });
    addEventListener("touchstart", onTouchStart, { passive: true });
    addEventListener("touchmove", onTouchMove, { passive: true });
    addEventListener("keydown", onKey);
    addEventListener("scroll", onScroll, { passive: true });
    return () => {
      removeEventListener("wheel", onWheel);
      removeEventListener("touchstart", onTouchStart);
      removeEventListener("touchmove", onTouchMove);
      removeEventListener("keydown", onKey);
      removeEventListener("scroll", onScroll);
    };
  }, []);

  const hidden = !visible;

  return (
    <header className={`site-header${visible ? " is-visible" : ""}`} aria-hidden={hidden} inert={hidden}>
      <section className="site-header-block">
        <h2 className="site-header-label">El proyecto</h2>
        <p>
          Simulamos cómo cambian el aire y la seguridad de las comunas de Santiago según los planes públicos
          que las afectan y la probabilidad real de que se cumplan. Así sabes dónde invertir con menos riesgo.
        </p>
      </section>
      <section className="site-header-block">
        <h2 className="site-header-label">Quiénes somos</h2>
        <p>Team 22 de Platanus Hack 26, track Simulaciones.</p>
        <ul className="site-header-team">
          {TEAM.map((m) => (
            <li key={m.github}>
              <a href={`https://github.com/${m.github}`} target="_blank" rel="noopener noreferrer">
                {m.name}
              </a>
            </li>
          ))}
        </ul>
      </section>
    </header>
  );
}
