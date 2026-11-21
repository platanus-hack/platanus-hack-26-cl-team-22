import { useCallback, useEffect, useRef, useState } from "react";
import { Logo } from "./Logo";
import { ScrollHint } from "./ScrollHint";
import { startIntro } from "./intro";
import type { IntroHandle } from "./intro";
import { Simulator } from "./simulator/Simulator";
import type { SimulatorApi } from "./simulator/engine";

type Sim = { api: SimulatorApi; root: HTMLElement };

export function App() {
  const spacerRef = useRef<HTMLDivElement>(null);
  const layerRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const introRef = useRef<IntroHandle | null>(null);
  const [sim, setSim] = useState<Sim | null>(null);

  const onReady = useCallback((api: SimulatorApi, root: HTMLElement) => setSim({ api, root }), []);
  const onHome = useCallback(() => introRef.current?.reopen(), []);

  // Runs right away (the letters can zoom before the globe has loaded) and
  // again once the simulator is ready to take over the period.
  useEffect(() => {
    const intro = startIntro({ spacer: spacerRef.current!, layer: layerRef.current!, box: boxRef.current!, sim });
    introRef.current = intro;
    return intro.dispose;
  }, [sim]);

  return (
    <>
      <div className="intro-spacer" ref={spacerRef} />
      <div className="logo-layer" ref={layerRef}>
        <Logo ref={boxRef} />
      </div>
      <Simulator onReady={onReady} onHome={onHome} />
      <ScrollHint />
    </>
  );
}
