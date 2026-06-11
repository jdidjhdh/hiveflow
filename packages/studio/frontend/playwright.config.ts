import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: 1,
  reporter: [['html', { outputFolder: 'playwright-report' }], ['list']],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: [
    {
      command: process.platform === 'win32'
        ? 'cd ..\\backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000'
        : 'cd ../backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        HIVEFLOW_RUNTIME: 'agent',
        HIVEFLOW_AGENT_ECHO_LLM: 'true',
        HIVEFLOW_PLAN_HITL: 'false',
      },
    },
    {
      command: 'npx vite --host',
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
