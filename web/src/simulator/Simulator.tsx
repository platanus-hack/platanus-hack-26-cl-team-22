import { memo, useEffect, useRef } from "react";
import "@fontsource-variable/bricolage-grotesque/opsz.css";
import "@fontsource-variable/instrument-sans";
import "./simulator.css";
import type { SimulatorApi } from "./engine";
import { entrarAlSimulador, URL_SIMULADOR } from "../simulador";

type Props = {
  /** Se llama una vez, cuando el motor (d3 + datos, carga diferida) está listo. */
  onReady: (api: SimulatorApi, root: HTMLDivElement) => void;
  /** Botón "Volver al inicio": de vuelta al logo. */
  onHome: () => void;
};

// Start downloading the engine as soon as this module is evaluated (in
// parallel with React's first render), not after the component mounts.
const engine = import("./engine");

// Marcado del "Simulador de comunas". El motor (engine.js) lo maneja de forma
// imperativa por id, así que React lo pinta una sola vez y no lo vuelve a tocar.
export const Simulator = memo(function Simulator({ onReady, onHome }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    engine.then(({ mountSimulator }) => {
      const root = rootRef.current;
      if (alive && root) onReady(mountSimulator(root, { startHidden: true }), root);
    });
    return () => {
      alive = false;
    };
  }, [onReady]);

  return (
    <div className="sim is-intro" data-level="world" ref={rootRef}>
      <main className="app">
        <section className="stage" id="stage">
          <canvas id="map" role="img" aria-label="Mapa interactivo: el mundo, con zoom hasta las comunas de Santiago"></canvas>

          <div className="brand">
            <button type="button" className="home" onClick={onHome}>
              ← Volver al inicio
            </button>
            <span>Platanus Hack 26, track Simulación</span>
          </div>

          <div className="intro">
            <h1>Mira hacia dónde va una comuna antes de comprar</h1>
            <p>Proyectamos el aire y la seguridad de cada comuna a 5, 10 y 30 años, según los planes públicos que la afectan y la probabilidad real de que se cumplan.</p>
            {/* El motor escucha este mismo botón y vuela a la región; al llegar se abre el simulador real. */}
            <button className="cta" id="cta" onClick={entrarAlSimulador}>
              Entrar al simulador
            </button>
            <small>O sigue bajando.</small>
          </div>

          <div className="zoom" aria-label="Zoom">
            <button id="zin" aria-label="Acercar">+</button>
            <button id="zout" aria-label="Alejar">−</button>
          </div>

          <div className="legend" aria-hidden="true">
            <b id="legendTitle">Puntaje a 10 años con tus pesos</b>
            <div className="ramp"></div>
            <div className="ends"><span>Peor</span><span>Mejor</span></div>
            <div className="ctx"><i></i>Sin simular todavía</div>
          </div>

          <nav className="crumbs" aria-label="Nivel de zoom">
            <button data-go="world">Mundo</button>
            <button data-go="country">Chile</button>
            <button data-go="region">Región Metropolitana</button>
            <button data-go="comuna" hidden></button>
          </nav>

          <a className="attr" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">Calles y lugares © colaboradores de OpenStreetMap</a>

          <div className="tip" id="tip"></div>
        </section>

        <aside className="panel" aria-label="Simulación">
          <div className="view" id="viewRank">
            <div className="head">
              <h2>Ranking de comunas</h2>
              <div className="seg" id="horizon" role="group" aria-label="Horizonte">
                <button data-h="5">5 años</button><button data-h="10">10 años</button><button data-h="30">30 años</button>
              </div>
            </div>

            <h3>Qué te importa más</h3>
            <div className="chips" id="profiles"></div>
            <div className="weights">
              <label className="w">Aire limpio <input type="range" min="0" max="100" id="wA" /><output id="oA" className="num"></output></label>
              <label className="w">Seguridad <input type="range" min="0" max="100" id="wS" /><output id="oS" className="num"></output></label>
              <label className="w">Barrio que crece <input type="range" min="0" max="100" id="wP" /><output id="oP" className="num"></output></label>
            </div>

            <label className="switch">
              <input type="checkbox" id="shock" />
              <div><b>Escenario: sanciones a Venezuela, más migración</b>
              <span>Su efecto es debatido. Entra como un rango y solo mueve la población, nunca la seguridad.</span></div>
            </label>

            <p className="why" id="why" aria-live="polite">Mueve un peso y aquí verás qué comunas suben o bajan, y por qué.</p>

            <ol className="rank" id="rank"></ol>

            <button className="link" id="openSrc">Ver las fuentes internacionales del modelo</button>

            <p className="note">Cifras de ejemplo para mostrar la interfaz: no sirven para decidir una compra. El modelo real se alimenta de SINCA, CEAD, ENUSC, Censo, PPDA y SEIA.</p>

            <a className="abrir" href={URL_SIMULADOR}>
              Abrir el simulador con datos reales
            </a>
          </div>

          <div className="view" id="viewSources" hidden>
            <button className="back" id="backSrc">‹ Volver al ranking</button>
            <h2>Fuentes internacionales</h2>
            <p className="sub">Los datos por comuna son chilenos. Estas fuentes dan la vara de comparación, la tendencia de fondo y el rango de los escenarios.</p>
            <div className="drivers" id="srcList" style={{ marginTop: 16 }}></div>
          </div>

          <div className="view" id="viewDetail" hidden>
            <button className="back" id="back">‹ Volver al ranking</button>
            <h2 id="dName"></h2>
            <p className="sub" id="dSub"></p>
            <div className="tabs seg" id="vars" role="group" aria-label="Variable">
              <button data-v="pm">Aire</button><button data-v="del">Seguridad</button><button data-v="pob">Población</button>
            </div>
            <div className="chart" id="chart"></div>
            <p className="read" id="read"></p>

            <h3>Referencia internacional</h3>
            <div className="drivers" id="intl"></div>

            <h3>Qué mueve esta proyección</h3>
            <div className="drivers" id="drivers"></div>

            <h3>Prueba retroactiva 2017 a 2024</h3>
            <div className="chart" id="vchart"></div>
            <p className="read" id="vread"></p>

            <p className="note">Son proyecciones con bandas de incertidumbre, no predicciones. Cifras de ejemplo.</p>
          </div>
        </aside>
      </main>
    </div>
  );
});
