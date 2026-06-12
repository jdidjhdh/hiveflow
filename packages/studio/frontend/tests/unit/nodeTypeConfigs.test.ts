import { describe, it, expect } from 'vitest';
import { translate } from '@/i18n';
import { buildDefaultNodeData, getNodeTypeConfigs } from '@/components/orchestrator/constants/nodeTypeConfigs';

const t = (key: Parameters<typeof translate>[1]) => translate('en', key);

describe('nodeTypeConfigs', () => {
  it('returns all node variants with english labels', () => {
    const configs = getNodeTypeConfigs(t);
    expect(configs).toHaveLength(9);
    expect(configs.map((c) => c.variant)).toContain('hitl');
    expect(configs[0].label).toBe('Task node');
  });

  it('buildDefaultNodeData sets variant-specific defaults', () => {
    const condition = buildDefaultNodeData(t, 'condition', 'Branch');
    expect(condition.condition_data?.branches).toHaveLength(2);
    expect(condition.condition_data?.branches?.[0].label).toBe('Yes');

    const hitl = buildDefaultNodeData(t, 'hitl', 'Approve');
    expect(hitl.hitl_config?.prompt).toBe('Please approve to continue');

    const code = buildDefaultNodeData(t, 'code', 'Run');
    expect(code.code_data?.code).toContain('function main');
  });
});
