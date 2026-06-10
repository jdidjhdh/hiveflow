import { test as base, expect, Page } from '@playwright/test';

// ====== Page Object: Orchestrator ======
export class OrchestratorPage {
  constructor(public page: Page) {}

  async goto() {
    await this.page.goto('/orchestrator');
    await this.page.waitForSelector('.react-flow', { timeout: 15000 });
  }

  async addNodeToCanvas(nodeVariant: string) {
    const variantMap: Record<string, string> = {
      'task': 'task', 'dynamic': 'dynamic', 'subgraph': 'subgraph',
      'condition': 'condition', 'loop': 'loop', 'code': 'code',
      'http': 'http', 'trigger': 'trigger',
    };
    const variant = variantMap[nodeVariant] || nodeVariant;
    
    // Use drag and drop to add node from panel to canvas
    const sourceSelector = `[data-testid="node-${variant}"]`;
    const targetSelector = '.react-flow';
    
    // Wait for both elements to be visible
    await expect(this.page.locator(sourceSelector)).toBeVisible({ timeout: 5000 });
    await expect(this.page.locator(targetSelector)).toBeVisible({ timeout: 5000 });
    
    // Use Playwright's dragAndDrop which properly fires HTML5 drag events
    await this.page.dragAndDrop(sourceSelector, targetSelector, {
      sourcePosition: { x: 50, y: 20 },
      targetPosition: { x: 400, y: 300 },
      timeout: 10000,
    });
    
    // Wait for the node to appear on canvas
    await expect(this.page.locator('.react-flow__node').first()).toBeVisible({ timeout: 5000 });
  }

  async clickNodeOnCanvas(index = 0) {
    await this.page.locator('.react-flow__node').nth(index).click();
  }

  async fillNodeConfig(fieldLabel: string, value: string) {
    await this.page.getByLabel(fieldLabel).fill(value);
  }

  async saveNodeConfig() {
    await this.page.getByRole('button', { name: 'Save' }).or(this.page.locator('button:has-text("保存")')).click();
    await this.page.waitForTimeout(500);
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
    await this.page.waitForTimeout(300);
    // Use first() to avoid strict mode violation when .or() matches both the li and the inner div
    await this.page.locator(`[data-testid="template-${templateKey}"]`).first().click();
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
    return await this.page.locator('.react-flow__node').count();
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
  orchestrator: async ({ page }, use) => {
    await use(new OrchestratorPage(page));
  },
  variables: async ({ page }, use) => {
    await use(new VariablesPage(page));
  },
});

export { expect };
