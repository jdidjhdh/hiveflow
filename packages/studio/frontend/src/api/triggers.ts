import { apiFetch } from './client';
import type { TriggerDef } from '@/types';

export function mapApiTrigger(raw: Record<string, unknown>): TriggerDef {
  return {
    id: String(raw.id || ''),
    name: String(raw.name || ''),
    type: (raw.type as TriggerDef['type']) || 'webhook',
    config: (raw.config as Record<string, unknown>) || {},
    enabled: Boolean(raw.enabled ?? true),
    workflow_id: typeof raw.workflow_id === 'string' ? raw.workflow_id : undefined,
    created_at: raw.created_at ? Number(raw.created_at) * 1000 : Date.now(),
  };
}

export async function listTriggers(): Promise<TriggerDef[]> {
  const data = await apiFetch('/api/triggers');
  return (data.triggers || []).map((t: Record<string, unknown>) => mapApiTrigger(t));
}

export async function createTrigger(trigger: Omit<TriggerDef, 'id' | 'created_at'>): Promise<TriggerDef> {
  const data = await apiFetch('/api/triggers', {
    method: 'POST',
    body: JSON.stringify(trigger),
  });
  return mapApiTrigger(data);
}

export async function updateTriggerApi(id: string, updates: Partial<TriggerDef>): Promise<TriggerDef> {
  const data = await apiFetch(`/api/triggers/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
  return mapApiTrigger(data);
}

export async function deleteTriggerApi(id: string): Promise<void> {
  await apiFetch(`/api/triggers/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export async function toggleTriggerApi(id: string): Promise<TriggerDef> {
  const data = await apiFetch(`/api/triggers/${encodeURIComponent(id)}/toggle`, { method: 'POST' });
  return mapApiTrigger(data);
}
