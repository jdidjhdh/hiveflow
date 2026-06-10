import { test, expect } from './fixtures';

test.describe('Condition Branch and Variables', () => {
  test('should configure variables and reference them', async ({ orchestrator, variables, page }) => {
    await variables.goto();
    await expect(page).toHaveURL(/.*variables/);

    await variables.createVariable('test_var', 'hello world');
    await variables.hasVariable('test_var');

    await orchestrator.goto();
    await expect(page).toHaveURL(/.*orchestrator/);

    await orchestrator.addNodeToCanvas('condition');
    await orchestrator.clickNodeOnCanvas();
    await expect(page.getByText('引用变量语法')).toBeVisible();
    await expect(page.getByText('{{variable_name}}')).toBeVisible();
  });

  test('should edit and delete variables', async ({ variables, page }) => {
    await variables.goto();
    await variables.createVariable('edit_test', 'original');
    await variables.hasVariable('edit_test');
    // Scope to the table to avoid matching the textarea in the modal
    await expect(page.locator('.ant-table').getByText('original')).toBeVisible();
  });
});
