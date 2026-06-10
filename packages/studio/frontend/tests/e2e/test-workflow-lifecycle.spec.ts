import { test, expect } from './fixtures';

test.describe('Workflow Complete Lifecycle', () => {
  test('should create workflow from template and execute', async ({ orchestrator, page }) => {
    await orchestrator.goto();
    await expect(page).toHaveTitle(/HiveFlow/);

    await orchestrator.loadTemplate('rag_pipeline');
    await expect(await orchestrator.getNodeCount()).toBeGreaterThan(0);

    await orchestrator.clickNodeOnCanvas(0);
    await expect(page.locator('.ant-drawer-open')).toBeVisible({ timeout: 5000 });

    await orchestrator.fillNodeConfig('节点名称', '测试检索节点');
    await orchestrator.saveNodeConfig();

    await orchestrator.executeWorkflow();
    await expect(page.getByTestId('btn-stop')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('btn-execute')).toBeVisible({ timeout: 30000 });
    await expect(page.getByText('工作流执行完成')).toBeVisible({ timeout: 10000 });
  });

  test('should create new canvas', async ({ orchestrator, page }) => {
    await orchestrator.goto();
    await orchestrator.loadTemplate('rag_pipeline');
    await expect(await orchestrator.getNodeCount()).toBeGreaterThan(0);

    await orchestrator.newCanvas();
    await expect(page.locator('.react-flow__node')).toHaveCount(0);
  });

  test('should show node library panel', async ({ orchestrator, page }) => {
    await orchestrator.goto();
    await expect(page.getByTestId('node-task')).toBeVisible();
    await expect(page.getByTestId('node-condition')).toBeVisible();
    await expect(page.getByTestId('node-code')).toBeVisible();
    await expect(page.getByTestId('node-http')).toBeVisible();
  });
});
