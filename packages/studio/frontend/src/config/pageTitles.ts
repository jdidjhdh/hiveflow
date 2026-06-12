import { useMemo } from 'react';
import type { MessageKey } from '@/i18n';
import { translate } from '@/i18n';
import { useLocaleStore, type StudioLocale } from '@/store/useLocaleStore';

const NAV_KEYS: Record<string, MessageKey> = {
  '/orchestrator': 'nav.orchestrator',
  '/agents': 'nav.agents',
  '/chatflow': 'nav.chatflow',
  '/analytics': 'nav.analytics',
  '/approvals': 'nav.approvals',
  '/dashboard': 'nav.dashboard',
  '/capabilities': 'nav.capabilities',
  '/knowledge': 'nav.knowledge',
  '/prompt-templates': 'nav.promptTemplates',
  '/ab-testing': 'nav.abTesting',
  '/audit-log': 'nav.auditLog',
  '/tracer': 'nav.tracer',
  '/replay': 'nav.replay',
  '/blackboard': 'nav.blackboard',
  '/events': 'nav.events',
  '/variables': 'nav.variables',
  '/triggers': 'nav.triggers',
  '/llm-config': 'nav.llmConfig',
  '/settings': 'nav.settings',
};

export function pageTitleForPath(pathname: string, locale: StudioLocale): string {
  const base = '/' + pathname.split('/').filter(Boolean)[0];
  const key = NAV_KEYS[base];
  return key ? translate(locale, key) : 'HiveFlow Studio';
}

export function usePageTitle(pathname: string): string {
  const locale = useLocaleStore((s) => s.locale);
  return useMemo(() => pageTitleForPath(pathname, locale), [pathname, locale]);
}
