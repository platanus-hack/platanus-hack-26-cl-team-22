import { defineConfig } from 'vitest/config'

// Separate from `npm test`: these cases call the real model through servidor-guia (see scripts/evaluar-casos.eval.ts).
export default defineConfig({
  test: { include: ['scripts/**/*.eval.ts'], environment: 'node', testTimeout: 180_000, hookTimeout: 30_000, fileParallelism: false },
})
