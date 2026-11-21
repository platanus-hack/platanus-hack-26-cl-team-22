// Construye la interfaz de viz/ y la copia a web/dist/simulador, para que la landing y el
// simulador se publiquen como un solo sitio estático. Lo llama `npm run build` de web/.
import { execSync } from "node:child_process";
import { cpSync, existsSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const web = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const viz = resolve(web, "../viz");
const destino = resolve(web, "dist/simulador");

if (!existsSync(resolve(web, "dist"))) {
  console.error("Falta web/dist: corre primero la construcción de la landing.");
  process.exit(1);
}

const correr = (cmd) => execSync(cmd, { cwd: viz, stdio: "inherit", env: { ...process.env, VITE_INICIO_URL: "../" } });

if (!existsSync(resolve(viz, "node_modules"))) correr("npm ci");
correr("npm run build");

rmSync(destino, { recursive: true, force: true });
cpSync(resolve(viz, "dist"), destino, { recursive: true });
console.log("Simulador copiado a web/dist/simulador");
