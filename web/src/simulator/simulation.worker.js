// Corre el Monte Carlo fuera del hilo principal y devuelve el resultado a engine.js.
import { runAll } from "./model.js";

postMessage(runAll());
