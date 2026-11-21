import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    // The simulator chunk (lazy-loaded) embeds the world maps and the
    // OpenStreetMap street extract for Santiago: ~2.5 MB by design.
    chunkSizeWarningLimit: 3000,
  },
});
