import { describe, it, expect } from 'vitest';
import { PAGE_CAPABILITIES, getPageCapability } from '@/config/pageCapabilities';

describe('pageCapabilities', () => {
  it('defines maturity for all studio pages', () => {
    expect(Object.keys(PAGE_CAPABILITIES).length).toBeGreaterThanOrEqual(10);
    expect(getPageCapability('orchestrator').maturity).toBe('stable');
    expect(getPageCapability('abTesting').alwaysDemo).toBe(true);
  });

  it('provides bilingual demo banner messages where configured', () => {
    const cap = getPageCapability('dashboard');
    expect(cap.bannerKey).toBe('maturity.banner.dashboard');
  });
});
