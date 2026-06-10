import { test, expect } from './fixtures';

test.describe('Code Execution Node', () => {
  test('should create and configure code execution node', async ({ orchestrator, page }) => {
    await orchestrator.goto();
    await orchestrator.addNodeToCanvas('code');
    await expect(await orchestrator.getNodeCount()).toBe(1);

    await orchestrator.clickNodeOnCanvas();
    await expect(page.locator('.ant-drawer-open')).toBeVisible();

    await expect(page.getByLabel('编程语言')).toBeVisible();
    await expect(page.getByLabel('代码')).toBeVisible();

    // The language selector is a Select component with "JavaScript" already selected by default
    // Just verify it's visible and move on to filling the code
    await expect(page.locator('#language')).toBeVisible();

    await page.getByLabel('代码').fill('return { result: 1 + 2 };');
    await orchestrator.saveNodeConfig();
  });
});

test.describe('Condition Branch and Variables', () => {
  test('should add condition node and configure branches', async ({ orchestrator, page }) => {
    await orchestrator.goto();
    await orchestrator.addNodeToCanvas('condition');
    await expect(await orchestrator.getNodeCount()).toBe(1);

    await orchestrator.clickNodeOnCanvas();
    await expect(page.locator('.ant-drawer-open')).toBeVisible();

    await expect(page.getByLabel('条件表达式')).toBeVisible();
    await expect(page.getByText('引用变量语法')).toBeVisible();

    await orchestrator.fillNodeConfig('条件表达式', '{{input.value}} > 10');
    await orchestrator.saveNodeConfig();
  });
});

test.describe('Import and Export', () => {
  test('should export workflow as .hflow file', async ({ orchestrator, page }) => {
    await orchestrator.goto();
    await orchestrator.loadTemplate('rag_pipeline');
    await expect(await orchestrator.getNodeCount()).toBeGreaterThan(0);

    const downloadPromise = page.waitForEvent('download', { timeout: 15000 });
    await orchestrator.exportWorkflow();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toContain('.hflow');
    const path = await download.path();
    expect(path).not.toBeNull();
  });
});

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
