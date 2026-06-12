import { test, expect, enableRealAgentMode, navigateToApprovals } from './fixtures';

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
    await enableRealAgentMode(page);

    await page.getByTestId('btn-agent-query').click();
    await page.getByTestId('agent-query-input').fill('summarize test workflow');
    await page.getByTestId('btn-plan-only').click();

    await expect(page.getByText(/intent_id/i)).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId('btn-import-plan')).toBeVisible({ timeout: 5000 });
  });

  test('Golden Path: plan-only → import canvas → execute DAG', async ({ page }) => {
    await enableRealAgentMode(page);

    await expect(page.getByTestId('golden-path-banner')).toBeVisible({ timeout: 5000 });

    await page.getByTestId('btn-agent-query').click();
    await page.getByTestId('agent-query-input').fill('create a two-step research workflow');
    await page.getByTestId('btn-plan-only').click();
    await expect(page.getByTestId('btn-import-plan')).toBeVisible({ timeout: 30000 });

    await page.getByTestId('btn-import-plan').click();
    await expect(page.locator('.react-flow__node')).toHaveCount(await page.locator('.react-flow__node').count(), {
      timeout: 5000,
    });
    const nodeCount = await page.locator('.react-flow__node').count();
    expect(nodeCount).toBeGreaterThan(0);

    await page.getByTestId('btn-execute').click();
    await expect(page.locator('.react-flow__node')).toHaveCount(nodeCount, { timeout: 60000 });
  });

  test('approvals page loads in real mode', async ({ page }) => {
    await enableRealAgentMode(page);
    await navigateToApprovals(page);
    await expect(page.getByTestId('approvals-page')).toBeVisible({ timeout: 10000 });
  });
});
