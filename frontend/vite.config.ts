/// <reference types="vitest/config" />
import path from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

const backend = process.env.BOARDINSIGHT_API ?? "http://127.0.0.1:8000";
// Manter o Host original: a API compara-o com o Origin para aceitar escritas da mesma origem.
const target = { target: backend, changeOrigin: false };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    host: "127.0.0.1",
    port: 5180,
    proxy: {
      "/api": target,
      "/health": target,
      "/ready": target,
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // Máquina de destino lenta (Atom): os testes de páginas com gráficos excedem os 5 s por omissão.
    testTimeout: 20000,
  },
});
