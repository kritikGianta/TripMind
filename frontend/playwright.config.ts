import { defineConfig } from "@playwright/test";

/**
 * End-to-end smoke tests against a running stack (docker compose up -d).
 * Uses the locally installed Chrome, so no browser download is needed:
 *   npm run e2e                       (BASE_URL defaults to http://localhost:3000)
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    channel: "chrome",
    trace: "retain-on-failure",
  },
});
