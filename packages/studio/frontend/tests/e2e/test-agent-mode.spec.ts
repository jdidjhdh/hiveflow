import { test, expect } from './fixtures';

/**
 * Agent mode E2E — requires Studio backend on :8000 (vite proxy).
 * Skip when backend unavailable.
 */
test.describe('Agent mode (real backend)', () => {
  test.beforeEach(async ({ page }) => {
    const health = await page.request.get('/api/health').catch(() => null);
    if (!health || !health.ok()) {
      const msg = 'Studio backend not running on :8000 (vite proxy /api)';
      if (process.env.CI) {
        throw new Error(msg);
      }
      test.skip(true, msg);
    }
  });

  test('plan-only returns plan JSON in orchestrator drawer', async ({ page }) => {
    await page.goto('/orchestrator');
    await page.waitForSelector('.react-flow', { timeout: 15000 });

    const realToggle = page.locator('.hf-header').getByRole('switch').first();
    if (await realToggle.isVisible()) {
      await realToggle.click();
      await page.waitForTimeout(500);
    }

    await page.getByTestId('btn-agent-query').click();
    await page.locator('textarea').first().fill('summarize test workflow');
    await page.getByRole('button', { name: /NL 生成草图/ }).click();

    await expect(page.getByText(/intent_id/i)).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('button', { name: /导入到画布/ })).toBeVisible({ timeout: 5000 });
  });

  test('approvals page loads in real mode', async ({ page }) => {
    await page.goto('/approvals');
    await expect(page.getByText(/待审批任务/)).toBeVisible({ timeout: 10000 });
  });
});
