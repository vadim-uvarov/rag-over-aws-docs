/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    // Playwright specs live under tests/e2e and run via `npm run test:e2e`.
    exclude: ["tests/e2e/**", "node_modules/**"],
  },
});
