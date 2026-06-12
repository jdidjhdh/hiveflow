import { test, expect } from './fixtures';

test.describe('Workflow Complete Lifecycle', () => {
  test('should add task node from node library', async ({ orchestrator }) => {
    await orchestrator.goto();
    await orchestrator.addNodeToCanvas('task');
    expect(await orchestrator.getNodeCount()).toBe(1);
  });

  test('should create workflow from template and execute', async ({ orchestrator, page }) => {
    await orchestrator.goto();
    await expect(page).toHaveTitle(/HiveFlow/);

    await orchestrator.loadTemplate('rag_pipeline');
    await expect(await orchestrator.getNodeCount()).toBeGreaterThan(0);

    await orchestrator.clickNodeOnCanvas(0);
    await expect(page.getByTestId('node-config-drawer')).toBeVisible({ timeout: 5000 });

    await orchestrator.fillNodeField('label', '测试检索节点');
    await orchestrator.saveNodeConfig();

    await orchestrator.executeWorkflow();
    await expect(page.getByTestId('btn-stop')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('btn-execute')).toBeVisible({ timeout: 30000 });
    await orchestrator.expectWorkflowCompleted();
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
