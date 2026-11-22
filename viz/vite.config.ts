import type { Plugin } from 'vite'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { IncomingMessage, ServerResponse } from 'node:http'

const aqui = path.dirname(fileURLToPath(import.meta.url))
const ejemplo = path.resolve(aqui, 'ejemplo/simulacion.json')
/** Salida del modelo (python -m experiments.simular). Si no existe, la app cae al ejemplo. */
const real = path.resolve(aqui, 'datos/simulacion.json')
/** La misma simulación corrida hasta 2040 (python -m experiments.simular --hasta 2040 --salida viz/datos/simulacion-15.json). */
const largo = path.resolve(aqui, 'datos/simulacion-15.json')

/** Sirve viz/ejemplo/simulacion.json como datos/ejemplo.json sin duplicarlo a mano. */
function servirEjemplo(): Plugin {
  const responder = (_req: IncomingMessage, res: ServerResponse) => {
    res.setHeader('content-type', 'application/json; charset=utf-8')
    fs.createReadStream(ejemplo).pipe(res)
  }
  return {
    name: 'servir-ejemplo',
    configureServer(server) {
      server.middlewares.use('/datos/ejemplo.json', responder)
      server.middlewares.use('/datos/simulacion.json', (_req: IncomingMessage, res: ServerResponse, next: () => void) => {
        if (!fs.existsSync(real)) return next()
        res.setHeader('content-type', 'application/json; charset=utf-8')
        fs.createReadStream(real).pipe(res)
      })
      server.middlewares.use('/datos/simulacion-15.json', (_req: IncomingMessage, res: ServerResponse, next: () => void) => {
        if (!fs.existsSync(largo)) return next()
        res.setHeader('content-type', 'application/json; charset=utf-8')
        fs.createReadStream(largo).pipe(res)
      })
    },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'datos/ejemplo.json', source: fs.readFileSync(ejemplo) })
      if (fs.existsSync(real)) {
        this.emitFile({ type: 'asset', fileName: 'datos/simulacion.json', source: fs.readFileSync(real) })
      }
      if (fs.existsSync(largo)) {
        this.emitFile({ type: 'asset', fileName: 'datos/simulacion-15.json', source: fs.readFileSync(largo) })
      }
    },
  }
}

export default defineConfig({
  base: './',
  plugins: [react(), servirEjemplo()],
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
})
