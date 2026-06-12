import type { TemplateItem } from '@/data/mockPromptTemplates.types';

const STORAGE_KEY = 'hf_mock_prompt_templates';

const SEED: TemplateItem[] = [
  {
    id: 'mock-general-1',
    name: '通用助手',
    category: 'general',
    description: '演示用通用对话模板',
    tags: ['demo', 'chat'],
    variables: ['user_query'],
    model_hints: ['gpt-4o-mini'],
    current_version: 1,
    total_versions: 1,
    created_at: Date.now() / 1000 - 86400,
    updated_at: Date.now() / 1000,
  },
  {
    id: 'mock-rag-1',
    name: 'RAG 问答',
    category: 'rag',
    description: '基于检索内容的问答模板（演示）',
    tags: ['demo', 'rag'],
    variables: ['context', 'question'],
    model_hints: ['gpt-4o'],
    current_version: 1,
    total_versions: 1,
    created_at: Date.now() / 1000 - 172800,
    updated_at: Date.now() / 1000,
  },
];

export type { TemplateItem };

export function loadMockPromptTemplates(): TemplateItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as TemplateItem[];
  } catch {
    // ignore
  }
  return [...SEED];
}

export function saveMockPromptTemplates(templates: TemplateItem[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(templates));
  } catch {
    // ignore
  }
}

export function getMockTemplateContent(id: string): string {
  if (id.includes('rag')) {
    return 'Context:\n{{context}}\n\nQuestion: {{question}}\n\nAnswer concisely.';
  }
  return 'You are a helpful assistant.\n\nUser: {{user_query}}';
}
