import { create } from 'zustand';
import type { LLMProviderConfig } from '@/types';
import { API_BASE_URL, apiFetch } from '@/utils/api';

interface LLMConfigState {
  providers: LLMProviderConfig[];
  addProvider: (provider: Omit<LLMProviderConfig, 'id'>) => void;
  updateProvider: (id: string, updates: Partial<LLMProviderConfig>) => void;
  deleteProvider: (id: string) => void;
  getProvider: (id: string) => LLMProviderConfig | undefined;
  reset: () => void;
  // 凭证管理 API
  listCredentials: () => Promise<Array<{ id: string; name: string; type: string; created_at: number }>>;
  createCredential: (name: string, type: string, value: string) => Promise<{ id: string }>;
  getCredentialValue: (credId: string) => Promise<string>;
  deleteCredential: (credId: string) => Promise<void>;
  // 测试 LLM 连接
  testConnection: (provider: LLMProviderConfig) => Promise<{ success: boolean; message: string }>;
}

// 凭证管理 API

let nextId = 1;

export const useLLMConfigStore = create<LLMConfigState>((set, get) => ({
  providers: [],

  addProvider: (provider) => {
    const newProvider: LLMProviderConfig = {
      ...provider,
      id: `llm_${nextId++}`,
    };
    set((s) => ({ providers: [...s.providers, newProvider] }));
  },

  updateProvider: (id, updates) => {
    set((s) => ({
      providers: s.providers.map((p) => (p.id === id ? { ...p, ...updates } : p)),
    }));
  },

  deleteProvider: (id) => {
    set((s) => ({
      providers: s.providers.filter((p) => p.id !== id),
    }));
  },

  getProvider: (id) => {
    return get().providers.find((p) => p.id === id);
  },

  reset: () => {
    set({ providers: [] });
    nextId = 1;
  },

  // 凭证管理 API 调用
  async listCredentials(): Promise<Array<{ id: string; name: string; type: string; created_at: number }>> {
    const data = await apiFetch('/api/credentials');
    return data.credentials;
  },

  async createCredential(name: string, type: string, value: string): Promise<{ id: string }> {
    return apiFetch('/api/credentials', {
      method: 'POST',
      body: JSON.stringify({ name, type, value }),
    });
  },

  async getCredentialValue(credId: string): Promise<string> {
    const data = await apiFetch(`/api/credentials/${credId}`);
    return data.value;
  },

  async deleteCredential(credId: string): Promise<void> {
    await apiFetch(`/api/credentials/${credId}`, {
      method: 'DELETE',
    });
  },

  // 测试 LLM 连接
  async testConnection(provider: LLMProviderConfig): Promise<{ success: boolean; message: string }> {
    const { getProvider } = get();
    let apiKey = '';

    if (provider.api_key_credential_id) {
      try {
        apiKey = await get().getCredentialValue(provider.api_key_credential_id);
      } catch {
        return { success: false, message: '无法获取 API Key' };
      }
    }

    try {
      let url = provider.base_url || '';
      switch (provider.provider) {
        case 'openai':
          url = url || 'https://api.openai.com/v1/chat/completions';
          break;
        case 'anthropic':
          url = url || 'https://api.anthropic.com/v1/messages';
          break;
        case 'ollama':
          url = url || 'http://localhost:11434/api/chat';
          break;
        default:
          if (!url) return { success: false, message: '请提供 Base URL' };
      }

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (apiKey) {
        if (provider.provider === 'anthropic') {
          headers['x-api-key'] = apiKey;
        } else {
          headers['Authorization'] = `Bearer ${apiKey}`;
        }
      }

      const body: Record<string, unknown> = {};
      switch (provider.provider) {
        case 'openai':
          body.model = provider.model_name;
          body.messages = [{ role: 'user', content: 'test' }];
          body.max_tokens = 10;
          break;
        case 'anthropic':
          body.model = provider.model_name;
          body.messages = [{ role: 'user', content: 'test' }];
          body.max_tokens = 10;
          break;
        case 'ollama':
          body.model = provider.model_name;
          body.messages = [{ role: 'user', content: 'test' }];
          body.stream = false;
          break;
        default:
          body.model = provider.model_name;
          body.messages = [{ role: 'user', content: 'test' }];
          body.max_tokens = 10;
      }

      const resp = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(10000),
      });

      if (resp.ok) {
        return { success: true, message: '连接成功' };
      } else {
        const errText = await resp.text().catch(() => '');
        return { success: false, message: `HTTP ${resp.status}: ${errText.slice(0, 200)}` };
      }
    } catch (err: any) {
      return { success: false, message: `连接失败: ${err.message}` };
    }
  },
}));
