import { defineConfig } from "@playwright/test";

// Smoke e2e against a mocked API (the spec intercepts /ask). Run locally with
// `npm run test:e2e`; not part of the main CI job (browsers are heavy there).
export default defineConfig({
  testDir: "./tests/e2e",
  use: { baseURL: "http://localhost:4173" },
  webServer: {
    command: "npm run build && npm run preview -- --port 4173",
    port: 4173,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
