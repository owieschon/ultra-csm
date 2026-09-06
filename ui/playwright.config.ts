import { defineConfig, devices } from "@playwright/test";

const localApi = process.env.ULTRA_E2E_LOCAL_API === "1";

export default defineConfig({
  testMatch: localApi ? "**/local-redraft.spec.ts" : undefined,
  testIgnore: localApi ? undefined : "**/local-redraft.spec.ts",
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  webServer: {
    command: localApi
      ? "NEXT_PUBLIC_UCSM_READONLY_DEMO=0 npm run build && node tests/serve-export.mjs"
      : "npm run build:e2e && node tests/serve-export.mjs",
    url: "http://127.0.0.1:4173/ui/",
    reuseExistingServer: false,
    timeout: 120_000,
  },
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: "mobile-chromium",
      use: {
        ...devices["Pixel 5"],
        viewport: { width: 390, height: 844 },
      },
    },
  ],
});
