import { describe, it, expect } from 'vitest';
import { translate } from '@/i18n';

describe('i18n', () => {
  it('translates zh keys', () => {
    expect(translate('zh', 'nav.orchestrator')).toBe('编排器');
    expect(translate('zh', 'app.title')).toBe('HiveFlow Studio');
  });

  it('translates en keys', () => {
    expect(translate('en', 'nav.orchestrator')).toBe('Orchestrator');
    expect(translate('en', 'app.mockMode')).toBe('Mock mode');
  });

  it('translates page body keys', () => {
    expect(translate('zh', 'pages.dashboard.title')).toBe('实时仪表盘');
    expect(translate('en', 'pages.dashboard.title')).toBe('Live Dashboard');
  });

  it('interpolates params', () => {
    expect(translate('zh', 'pages.variables.totalCount', { count: 5 })).toBe('共 5 个变量');
    expect(translate('en', 'pages.variables.totalCount', { count: 5 })).toBe('5 variables total');
  });

  it('translates orchestrator keys', () => {
    expect(translate('zh', 'orchestrator.toolbar.newCanvas')).toBe('新建');
    expect(translate('en', 'orchestrator.toolbar.newCanvas')).toBe('New');
  });

  it('falls back to key for missing path', () => {
    expect(translate('zh', 'missing.key' as 'nav.orchestrator')).toBe('missing.key');
  });
});
