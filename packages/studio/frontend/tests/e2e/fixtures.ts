import { test as base, expect, Page } from '@playwright/test';

const LOCALE_STORAGE_KEY = 'hiveflow-studio-locale';

/** Pin zh locale so persisted user settings do not break selectors. */
export async function seedStudioLocale(page: Page, locale: 'zh' | 'en' = 'zh') {
  await page.addInitScript(
    ({ key, value, dbName }) => {
      localStorage.setItem(key, JSON.stringify({ state: { locale: value }, version: 0 }));
      (window as unknown as { __HF_IDB_READY__: Promise<boolean> }).__HF_IDB_READY__ = new Promise((resolve) => {
        const req = indexedDB.deleteDatabase(dbName);
        req.onsuccess = () => resolve(true);
        req.onerror = () => resolve(false);
        req.onblocked = () => resolve(false);
      });
    },
    { key: LOCALE_STORAGE_KEY, value: locale, dbName: 'HiveFlowStudio' },
  );
}

export async function enableRealAgentMode(page: Page) {
  await page.goto('/orchestrator');
  await page.waitForSelector('.react-flow', { timeout: 15000 });

  const realToggle = page.getByTestId('engine-mode-switch');
  if (await realToggle.isVisible()) {
    const checked = await realToggle.getAttribute('aria-checked');
    if (checked !== 'true') {
      await realToggle.click();
      await page.waitForTimeout(400);
    }
  }

  const runtimeSwitch = page.getByTestId('runtime-mode-switch');
  if (await runtimeSwitch.isVisible()) {
    const checked = await runtimeSwitch.getAttribute('aria-checked');
    if (checked !== 'true') {
      await runtimeSwitch.click();
      await page.waitForTimeout(400);
    }
  }
}

export async function navigateToApprovals(page: Page) {
  await page.getByRole('menuitem', { name: /人工审批|Approvals/ }).click();
  await page.waitForURL(/\/approvals/);
}
export class OrchestratorPage {
  constructor(public page: Page) {}

  async goto() {
    await this.page.goto('/orchestrator');
    await this.page.waitForFunction(() => (window as unknown as { __HF_IDB_READY__?: Promise<boolean> }).__HF_IDB_READY__ !== undefined);
    await this.page.evaluate(async () => {
      const ready = (window as unknown as { __HF_IDB_READY__?: Promise<boolean> }).__HF_IDB_READY__;
      if (ready) await ready;
    });
    await this.page.waitForSelector('.react-flow', { timeout: 15000 });
    await this.page.waitForSelector('.react-flow__renderer', { timeout: 15000 });
    await this.page.waitForSelector('[data-testid="orchestrator-ready"]', { timeout: 15000 });
  }

  async addNodeToCanvas(nodeVariant: string) {
    const variantMap: Record<string, string> = {
      task: 'task', dynamic: 'dynamic', subgraph: 'subgraph',
      condition: 'condition', loop: 'loop', code: 'code',
      http: 'http', trigger: 'trigger',
    };
    const variant = variantMap[nodeVariant] || nodeVariant;

    const addBtn = this.page.getByTestId(`btn-add-${variant}`);
    await expect(addBtn).toBeVisible({ timeout: 5000 });
    const before = await this.page.locator('.react-flow__node').count();
    await addBtn.click({ force: true });
    await expect(this.page.locator('.react-flow__node')).toHaveCount(before + 1, { timeout: 15000 });
  }

  async clickNodeOnCanvas(index = 0) {
    await this.page.locator('.react-flow__node').nth(index).click();
  }

  async clickCanvasNode(nodeId: string) {
    await this.page.getByTestId(`canvas-node-${nodeId}`).click();
  }

  async loadSandboxTemplate() {
    await this.loadTemplate('e2e_sandbox');
    await expect(this.page.getByTestId('canvas-node-e2e_code')).toBeVisible({ timeout: 5000 });
    await expect(this.page.getByTestId('canvas-node-e2e_condition')).toBeVisible({ timeout: 5000 });
  }

  async fillNodeField(field: 'label' | 'condition' | 'code' | 'task', value: string) {
    await this.page.getByTestId(`input-node-${field}`).fill(value);
  }

  async saveNodeConfig() {
    await this.page.getByTestId('btn-save-node-config').click();
    await expect(this.page.locator('.ant-drawer-open')).toHaveCount(0, { timeout: 5000 });
  }

  async executeWorkflow() {
    await this.page.getByTestId('btn-execute').click();
  }

  async stopExecution() {
    await this.page.getByTestId('btn-stop').click();
  }

  async newCanvas() {
    await this.page.getByTestId('btn-new').click();
  }

  async loadTemplate(templateKey: string) {
    await this.page.getByTestId('btn-template').click();
    const item = this.page.getByTestId(`template-${templateKey}`);
    await expect(item).toBeVisible({ timeout: 5000 });
    await item.click();
  }

  async exportWorkflow() {
    await this.page.getByTestId('btn-export').click();
  }

  async importWorkflow() {
    await this.page.getByTestId('btn-import').click();
  }

  async batchExportWorkflows() {
    await this.page.getByTestId('btn-batch-export').click();
  }

  async getNodeCount() {
    return this.page.locator('.react-flow__node').count();
  }

  async expectWorkflowCompleted(timeout = 30000) {
    await expect(
      this.page.locator('.ant-message-success').filter({ hasText: /工作流执行完成|Workflow completed/ }),
    ).toBeVisible({ timeout });
  }
}

// ====== Page Object: Variables ======
export class VariablesPage {
  constructor(public page: Page) {}

  async goto() {
    await this.page.goto('/variables');
    await this.page.waitForSelector('[data-testid="variables-page"]', { timeout: 15000 });
  }

  async createVariable(name: string, value: string) {
    await this.page.getByTestId('btn-add-variable').click();
    await this.page.getByTestId('input-var-name').fill(name);
    await this.page.getByTestId('input-var-value').fill(value);
    await this.page.getByTestId('btn-var-confirm').click();
    await this.page.waitForTimeout(500);
  }

  async hasVariable(name: string) {
    await expect(this.page.getByText(name)).toBeVisible({ timeout: 5000 });
  }
}

// ====== Fixtures ======
export const test = base.extend<{
  orchestrator: OrchestratorPage;
  variables: VariablesPage;
}>({
  page: async ({ page }, use) => {
    await seedStudioLocale(page, 'zh');
    await use(page);
  },
  orchestrator: async ({ page }, use) => {
    await use(new OrchestratorPage(page));
  },
  variables: async ({ page }, use) => {
    await use(new VariablesPage(page));
  },
});

export { expect };
