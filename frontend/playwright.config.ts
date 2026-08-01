import { defineConfig, devices } from '@playwright/test'

const e2ePort = process.env.E2E_PORT ?? '8765'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: 'list',
  timeout: 60_000,
  use: {
    baseURL: `http://127.0.0.1:${e2ePort}`,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'bash ../scripts/e2e-serve.sh',
    url: `http://127.0.0.1:${e2ePort}/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
