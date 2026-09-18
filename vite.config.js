import { defineConfig } from "vite";

export default defineConfig({
  root: "frontend",
  base: "/static/dist/",
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: "../static/dist", emptyOutDir: true, chunkSizeWarningLimit: 1800 },
});
