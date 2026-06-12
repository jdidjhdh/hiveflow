import { apiFetch } from './client';
import type { Capability } from '@/types';

export function mapApiAgent(raw: Record<string, unknown>): Capability {
  const agentId = String(raw.agent_id || '');
  return {
    agent_id: agentId,
    display_name: String(raw.display_name || agentId),
    description: typeof raw.description === 'string' ? raw.description : '',
    icon: '',
    skills: Array.isArray(raw.skills) ? raw.skills.map(String) : [],
    load: Number(raw.load ?? 0),
    pending_tasks: Number(raw.pending_tasks ?? 0),
    state: (raw.state as Capability['state']) || 'running',
    read_keys: Array.isArray(raw.read_keys) ? raw.read_keys.map(String) : [],
    write_keys: Array.isArray(raw.write_keys) ? raw.write_keys.map(String) : [],
    history: [],
    load_history: Array.isArray(raw.load_history)
      ? raw.load_history.map((p: Record<string, unknown>) => ({
          time: Number(p.time ?? 0),
          load: Number(p.load ?? 0),
        }))
      : [],
    recent_tasks: Array.isArray(raw.recent_tasks)
      ? raw.recent_tasks.map((t: Record<string, unknown>) => ({
          intent_id: String(t.intent_id || ''),
          status: String(t.status || 'success') as 'success' | 'failed' | 'timeout',
          timestamp: Number(t.timestamp ?? 0),
          duration: Number(t.duration ?? 0),
        }))
      : [],
    weight: Number(raw.weight ?? 1),
    task_handler: typeof raw.task_handler === 'string' ? raw.task_handler : '',
    last_heartbeat: Number(raw.last_heartbeat ?? Date.now() / 1000),
  };
}

export async function listAgents(): Promise<Capability[]> {
  const data = await apiFetch('/api/agents');
  return (data.agents || []).map((a: Record<string, unknown>) => mapApiAgent(a));
}

export async function registerAgent(body: Record<string, unknown>): Promise<void> {
  await apiFetch('/api/agents', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function drainAgent(agentId: string): Promise<void> {
  await apiFetch(`/api/agents/${encodeURIComponent(agentId)}/drain`, { method: 'POST' });
}

export async function stopAgent(agentId: string): Promise<void> {
  await apiFetch(`/api/agents/${encodeURIComponent(agentId)}`, { method: 'DELETE' });
}
