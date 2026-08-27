/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv } from "vite";

const DEFAULT_PORT = 5285;
const DEFAULT_API = "http://localhost:8285";

/**
 * One config for dev, build and test, so the path alias and the plugin list cannot drift apart.
 *
 * The dev server proxies `/api` so the browser only ever talks to one origin. In the container
 * nginx does the same job, which is why the app never needs to know the backend's address.
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env["SIDRA_API_URL"] ?? DEFAULT_API;
  return {
    plugins: [react()],
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    server: {
      port: Number(env["SIDRA_FRONTEND_PORT"] ?? DEFAULT_PORT),
      strictPort: true,
      proxy: {
        "/api": { target, changeOrigin: true },
        "/health": { target, changeOrigin: true },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./tests/setup.ts"],
      include: ["tests/**/*.test.{ts,tsx}"],
      coverage: {
        provider: "v8",
        reporter: ["text", "html"],
        include: ["src/**/*.{ts,tsx}"],
        exclude: ["src/main.tsx", "src/**/*.d.ts", "src/types/**"],
        thresholds: { lines: 100, functions: 100, branches: 100, statements: 100 },
      },
    },
  };
});
