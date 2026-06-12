import { describe, it, expect } from 'vitest';
import { buildMenuItems } from '@/config/menuItems';
import { translate } from '@/i18n';

describe('buildMenuItems', () => {
  it('returns primary and advanced groups', () => {
    const t = (key: Parameters<typeof translate>[1]) => translate('zh', key);
    const items = buildMenuItems(t);
    expect(items?.length).toBeGreaterThan(6);
    expect(items?.some((i) => i && 'key' in i && i.key === '/orchestrator')).toBe(true);
  });
});
