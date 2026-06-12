/** Single source of truth for Studio page maturity — see packages/studio/CAPABILITIES.md */

import type { MessageKey } from '@/i18n';

export type PageMaturity = 'stable' | 'beta' | 'preview' | 'demo';

export type PageCapabilityKey =
  | 'orchestrator'
  | 'agents'
  | 'chatflow'
  | 'approvals'
  | 'variables'
  | 'triggers'
  | 'capabilities'
  | 'dashboard'
  | 'analytics'
  | 'tracer'
  | 'replay'
  | 'blackboard'
  | 'events'
  | 'llmConfig'
  | 'knowledge'
  | 'promptTemplates'
  | 'abTesting'
  | 'auditLog'
  | 'settings';

export interface PageCapability {
  route: string;
  maturity: PageMaturity;
  /** Always show demo-data banner (regardless of engine mode). */
  alwaysDemo?: boolean;
  /** Show DemoDataBanner when engine is in mock mode. */
  mockBanner?: boolean;
  /** i18n key under maturity.banner.* */
  bannerKey?: MessageKey;
}

export const PAGE_CAPABILITIES: Record<PageCapabilityKey, PageCapability> = {
  orchestrator: { route: '/orchestrator', maturity: 'stable' },
  agents: { route: '/agents', maturity: 'stable' },
  chatflow: { route: '/chatflow', maturity: 'beta' },
  approvals: { route: '/approvals', maturity: 'stable' },
  variables: {
    route: '/variables',
    maturity: 'beta',
    mockBanner: true,
    bannerKey: 'maturity.banner.variables',
  },
  triggers: {
    route: '/triggers',
    maturity: 'beta',
    mockBanner: true,
    bannerKey: 'maturity.banner.triggers',
  },
  capabilities: {
    route: '/capabilities',
    maturity: 'beta',
    mockBanner: true,
    bannerKey: 'maturity.banner.capabilities',
  },
  dashboard: {
    route: '/dashboard',
    maturity: 'beta',
    mockBanner: true,
    bannerKey: 'maturity.banner.dashboard',
  },
  analytics: {
    route: '/analytics',
    maturity: 'preview',
    mockBanner: true,
    bannerKey: 'maturity.banner.analytics',
  },
  tracer: {
    route: '/tracer',
    maturity: 'beta',
    mockBanner: true,
    bannerKey: 'maturity.banner.tracer',
  },
  replay: { route: '/replay', maturity: 'beta' },
  blackboard: { route: '/blackboard', maturity: 'stable' },
  events: { route: '/events', maturity: 'stable' },
  llmConfig: {
    route: '/llm-config',
    maturity: 'beta',
    mockBanner: true,
    bannerKey: 'maturity.banner.llmConfig',
  },
  knowledge: {
    route: '/knowledge',
    maturity: 'beta',
    mockBanner: true,
    bannerKey: 'maturity.banner.knowledge',
  },
  promptTemplates: {
    route: '/prompt-templates',
    maturity: 'preview',
    mockBanner: true,
    bannerKey: 'maturity.banner.promptTemplates',
  },
  abTesting: {
    route: '/ab-testing',
    maturity: 'demo',
    alwaysDemo: true,
    bannerKey: 'maturity.banner.abTesting',
  },
  auditLog: {
    route: '/audit-log',
    maturity: 'beta',
    bannerKey: 'maturity.banner.auditLog',
  },
  settings: { route: '/settings', maturity: 'beta' },
};

export function getPageCapability(key: PageCapabilityKey): PageCapability {
  return PAGE_CAPABILITIES[key];
}
