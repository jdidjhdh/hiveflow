import { describe, it, expect } from 'vitest';
import { pageTitleForPath } from '@/config/pageTitles';

describe('pageTitleForPath', () => {
  it('returns translated nav title for known routes', () => {
    expect(pageTitleForPath('/orchestrator', 'zh')).toBe('编排器');
    expect(pageTitleForPath('/orchestrator', 'en')).toBe('Orchestrator');
    expect(pageTitleForPath('/variables/extra', 'en')).toBe('Variables');
  });

  it('falls back to app title for unknown routes', () => {
    expect(pageTitleForPath('/unknown-page', 'en')).toBe('HiveFlow Studio');
  });
});
