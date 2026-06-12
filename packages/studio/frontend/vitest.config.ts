import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.ts', 'tests/unit/**/*.test.tsx', 'src/**/*.test.ts', 'src/**/*.test.tsx'],
    setupFiles: './tests/setup.ts',
    // Reduce OOM on Windows when running full suite + coverage
    pool: 'forks',
    maxWorkers: 2,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'json-summary', 'html', 'lcov'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/main.tsx',
        'src/types/**',
        // Pages + orchestrator hooks: covered by Playwright E2E (see docs/en/quality-gates.md)
        'src/pages/**',
        'src/components/orchestrator/hooks/**',
      ],
      thresholds: {
        lines: 24,
        statements: 24,
        branches: 12,
        functions: 16,
        'src/utils/planToWorkflow.ts': {
          lines: 90,
          functions: 90,
          branches: 65,
          statements: 90,
        },
        'src/utils/chatflowTopology.ts': {
          lines: 75,
          functions: 100,
          branches: 35,
          statements: 75,
        },
        'src/api/client.ts': {
          lines: 55,
          functions: 60,
          branches: 35,
          statements: 55,
        },
        'src/i18n/index.ts': {
          lines: 85,
          functions: 85,
          branches: 80,
          statements: 85,
        },
        'src/config/pageCapabilities.ts': {
          lines: 90,
          functions: 100,
          branches: 80,
          statements: 90,
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
