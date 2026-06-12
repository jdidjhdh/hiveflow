import { describe, it, expect } from 'vitest';
import { translate } from '@/i18n';
import {
  getBuiltinTemplates,
  templateData,
  TEMPLATE_KEYS,
  PRODUCTION_TEMPLATE_KEYS,
  shouldShowE2eTemplates,
} from '@/components/orchestrator/constants/templates';

const t = (key: Parameters<typeof translate>[1]) => translate('en', key);

describe('orchestrator templates', () => {
  it('lists production templates by default in unit tests when e2e flag is off', () => {
    const templates = getBuiltinTemplates(t);
    const expectedCount = shouldShowE2eTemplates() ? TEMPLATE_KEYS.length : PRODUCTION_TEMPLATE_KEYS.length;
    expect(templates).toHaveLength(expectedCount);
    expect(templates[0].label).toBe('RAG pipeline');
  });

  it('hides e2e sandbox from production template menu', () => {
    if (shouldShowE2eTemplates()) {
      expect(getBuiltinTemplates(t).some((item) => item.key === 'e2e_sandbox')).toBe(true);
      return;
    }
    expect(getBuiltinTemplates(t).some((item) => item.key === 'e2e_sandbox')).toBe(false);
  });

  it('provides graph data for each template key', () => {
    for (const key of TEMPLATE_KEYS) {
      expect(templateData[key]?.nodes.length).toBeGreaterThan(0);
      if (key !== 'e2e_sandbox') {
        expect(templateData[key]?.edges.length).toBeGreaterThan(0);
      }
    }
  });
});
