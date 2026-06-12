import type { MessageKey, TranslateParams } from '@/i18n';

type TFn = (key: MessageKey, params?: TranslateParams) => string;

export const PRODUCTION_TEMPLATE_KEYS = ['rag_pipeline', 'debate_decision', 'hierarchical_planning'] as const;
export const E2E_ONLY_TEMPLATE_KEYS = ['e2e_sandbox'] as const;
export const TEMPLATE_KEYS = [...PRODUCTION_TEMPLATE_KEYS, ...E2E_ONLY_TEMPLATE_KEYS] as const;

export type TemplateKey = (typeof TEMPLATE_KEYS)[number];

export function shouldShowE2eTemplates(): boolean {
  return import.meta.env.DEV || import.meta.env.VITE_E2E === 'true';
}

export function getBuiltinTemplates(t: TFn): { key: TemplateKey; label: string; description: string }[] {
  const items: { key: TemplateKey; label: string; description: string }[] = [
    {
      key: 'rag_pipeline',
      label: t('orchestrator.templates.rag.label'),
      description: t('orchestrator.templates.rag.description'),
    },
    {
      key: 'debate_decision',
      label: t('orchestrator.templates.debate.label'),
      description: t('orchestrator.templates.debate.description'),
    },
    {
      key: 'hierarchical_planning',
      label: t('orchestrator.templates.hierarchical.label'),
      description: t('orchestrator.templates.hierarchical.description'),
    },
    {
      key: 'e2e_sandbox',
      label: t('orchestrator.templates.e2e.label'),
      description: t('orchestrator.templates.e2e.description'),
    },
  ];

  return shouldShowE2eTemplates()
    ? items
    : items.filter((item) => item.key !== 'e2e_sandbox');
}

export { templateData } from './templateData';
