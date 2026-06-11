import { create } from 'zustand';
import { apiFetch } from '@/utils/api';

export type RuntimeMode = 'core' | 'agent';

interface AgentRuntimeState {
  runtimeMode: RuntimeMode;
  agentActive: boolean;
  skills: string[];
  loading: boolean;
  lastAnswer: string;
  lastIntentId: string;
  lastStatus: string;
  fetchRuntime: () => Promise<void>;
  setRuntimeMode: (mode: RuntimeMode) => Promise<void>;
  runQuery: (query: string, conversationId?: string) => Promise<Record<string, unknown>>;
  planOnly: (query: string, conversationId?: string) => Promise<Record<string, unknown>>;
  executePlan: (
    plan: Record<string, unknown>,
    query?: string,
    conversationId?: string,
  ) => Promise<Record<string, unknown>>;
  exportLangGraph: (
    plan: Record<string, unknown>,
    options?: { workflowId?: string; includePython?: boolean },
  ) => Promise<{ spec: Record<string, unknown>; spec_json: string; python?: string; node_count: number }>;
}

export const useAgentRuntimeStore = create<AgentRuntimeState>((set) => ({
  runtimeMode: 'core',
  agentActive: false,
  skills: [],
  loading: false,
  lastAnswer: '',
  lastIntentId: '',
  lastStatus: '',

  fetchRuntime: async () => {
    try {
      const info = await apiFetch('/api/agent/runtime');
      set({
        runtimeMode: info.runtime_mode === 'agent' ? 'agent' : 'core',
        agentActive: Boolean(info.agent_active),
        skills: info.skills || [],
      });
    } catch {
      // 模拟模式或未连接后端
    }
  },

  setRuntimeMode: async (mode) => {
    set({ loading: true });
    try {
      const info = await apiFetch('/api/agent/runtime', {
        method: 'POST',
        body: JSON.stringify({ mode }),
      });
      set({
        runtimeMode: info.runtime_mode === 'agent' ? 'agent' : 'core',
        agentActive: Boolean(info.agent_active),
        skills: info.skills || [],
        loading: false,
      });
    } catch (e) {
      set({ loading: false });
      throw e;
    }
  },

  runQuery: async (query, conversationId) => {
    const result = await apiFetch('/api/agent/query', {
      method: 'POST',
      body: JSON.stringify({ query, conversation_id: conversationId }),
    });
    set({
      lastAnswer: String(result.answer ?? ''),
      lastIntentId: String(result.intent_id ?? ''),
      lastStatus: String(result.status ?? 'completed'),
    });
    return result;
  },

  planOnly: async (query, conversationId) => {
    const result = await apiFetch('/api/agent/plan-only', {
      method: 'POST',
      body: JSON.stringify({ query, conversation_id: conversationId }),
    });
    set({
      lastIntentId: String(result.intent_id ?? ''),
      lastStatus: String(result.status ?? 'planned'),
    });
    return result;
  },

  executePlan: async (plan, query = 'Execute workflow from canvas', conversationId) => {
    const result = await apiFetch('/api/agent/execute-plan', {
      method: 'POST',
      body: JSON.stringify({ plan, query, conversation_id: conversationId }),
    });
    set({
      lastAnswer: String(result.answer ?? ''),
      lastIntentId: String(result.intent_id ?? ''),
      lastStatus: String(result.status ?? 'completed'),
    });
    return result;
  },

  exportLangGraph: async (plan, options) => {
    return apiFetch('/api/agent/export-langgraph', {
      method: 'POST',
      body: JSON.stringify({
        plan,
        workflow_id: options?.workflowId ?? 'studio_export',
        include_python: options?.includePython ?? false,
      }),
    });
  },
}));
