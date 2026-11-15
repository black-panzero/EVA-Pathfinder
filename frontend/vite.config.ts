import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = process.env.EVA_API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react()],
  worker: { format: "es" },
  server: { port: 5173, proxy: { "/api": api, "/health": api } },
  preview: { port: 4173, proxy: { "/api": api, "/health": api } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./tests/setup.ts"], include: ["tests/**/*.test.ts?(x)"] },
});
