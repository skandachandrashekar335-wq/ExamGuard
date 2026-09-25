import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 60000,
  expect: { timeout: 10000 },
  use: {
    baseURL: process.env.EG_BASE_URL || "https://exam-guardian-management.vercel.app",
    headless: false,
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
  workers: 1,
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
  ],
});