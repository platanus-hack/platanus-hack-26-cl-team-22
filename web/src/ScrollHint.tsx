import { useEffect, useState } from "react";

const IDLE_MS = 3000;
const ACTIVITY = ["scroll", "wheel", "touchstart", "touchmove", "pointerdown", "pointermove", "keydown"] as const;

/**
 * "Scroll down" cue: appears after IDLE_MS without any interaction while the
 * intro is still on screen, and disappears with the first input.
 */
export function ScrollHint() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let timer = 0;
    const arm = () => {
      clearTimeout(timer);
      timer = window.setTimeout(() => {
        // Once the simulator has taken over there is nothing left to scroll.
        if (!document.body.classList.contains("sim-on")) setVisible(true);
      }, IDLE_MS);
    };
    const onActivity = () => {
      setVisible(false);
      arm();
    };
    ACTIVITY.forEach((type) => addEventListener(type, onActivity, { passive: true }));
    arm();
    return () => {
      clearTimeout(timer);
      ACTIVITY.forEach((type) => removeEventListener(type, onActivity));
    };
  }, []);

  return (
    <div className={`scroll-hint${visible ? " is-visible" : ""}`} aria-hidden={!visible}>
      <span className="scroll-hint-text">Desliza para explorar</span>
      <svg className="scroll-hint-icon" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
        <rect x="7" y="2.5" width="10" height="19" rx="5" />
        <path className="scroll-hint-wheel" d="M12 7v3" />
      </svg>
    </div>
  );
}
