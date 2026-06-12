import { apiFetch } from './client';

export interface AgentRuntimeInfo {
  runtime_mode: string;
  agent_active: boolean;
  skills: string[];
}

export async function getAgentRuntime(): Promise<AgentRuntimeInfo> {
  return apiFetch('/api/agent/runtime');
}

export async function setAgentRuntime(mode: 'core' | 'agent'): Promise<AgentRuntimeInfo> {
  return apiFetch('/api/agent/runtime', {
    method: 'POST',
    body: JSON.stringify({ mode }),
  });
}

export async function agentQuery(
  query: string,
  conversationId?: string,
): Promise<Record<string, unknown>> {
  return apiFetch('/api/agent/query', {
    method: 'POST',
    body: JSON.stringify({ query, conversation_id: conversationId }),
  });
}

export async function agentPlanOnly(
  query: string,
  conversationId?: string,
): Promise<Record<string, unknown>> {
  return apiFetch('/api/agent/plan-only', {
    method: 'POST',
    body: JSON.stringify({ query, conversation_id: conversationId }),
  });
}

export async function agentExecutePlan(
  plan: Record<string, unknown>,
  query?: string,
  conversationId?: string,
): Promise<Record<string, unknown>> {
  return apiFetch('/api/agent/execute-plan', {
    method: 'POST',
    body: JSON.stringify({ plan, query, conversation_id: conversationId }),
  });
}

export async function exportLangGraph(
  plan: Record<string, unknown>,
  options?: { workflow_id?: string; include_python?: boolean },
): Promise<{ spec: Record<string, unknown>; spec_json: string; python?: string; node_count: number }> {
  return apiFetch('/api/agent/export-langgraph', {
    method: 'POST',
    body: JSON.stringify({
      plan,
      workflow_id: options?.workflow_id,
      include_python: options?.include_python ?? false,
    }),
  });
}
