import type { LLMProviderConfig } from '@/types';

const MOCK_PROVIDERS_KEY = 'hf_mock_llm_providers';

export interface MockAgentSettings {
  use_echo_llm: boolean;
  planning_provider_id: string;
  execution_provider_id: string;
  llm_source: string;
  agent_active: boolean;
}

export const MOCK_AGENT_SETTINGS: MockAgentSettings = {
  use_echo_llm: true,
  planning_provider_id: 'mock-echo',
  execution_provider_id: 'mock-echo',
  llm_source: 'echo',
  agent_active: false,
};

export function loadMockProviders(): LLMProviderConfig[] {
  try {
    const raw = localStorage.getItem(MOCK_PROVIDERS_KEY);
    if (raw) return JSON.parse(raw) as LLMProviderConfig[];
  } catch {
    // ignore
  }
  return [
    {
      id: 'mock-echo',
      name: 'Echo 演示',
      provider: 'custom',
      model_name: 'echo',
      base_url: '',
      temperature: 0.7,
      max_tokens: 4096,
      top_p: 1,
    },
  ];
}

export function saveMockProviders(providers: LLMProviderConfig[]) {
  try {
    localStorage.setItem(MOCK_PROVIDERS_KEY, JSON.stringify(providers));
  } catch {
    // ignore
  }
}
