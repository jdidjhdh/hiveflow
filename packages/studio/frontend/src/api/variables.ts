import { apiFetch } from './client';
import type { VariableDef } from '@/types';

function toApiVarType(type: VariableDef['type']): string {
  if (type === 'object' || type === 'array') return 'json';
  return type;
}

function fromApiVarType(varType: string, value: unknown): VariableDef['type'] {
  if (varType === 'json') {
    return Array.isArray(value) ? 'array' : 'object';
  }
  if (varType === 'number' || varType === 'boolean' || varType === 'string') {
    return varType;
  }
  return 'string';
}

export function mapApiVariable(raw: Record<string, unknown>): VariableDef {
  const name = String(raw.name || '');
  const value = raw.value;
  const varType = String(raw.var_type || 'string');
  return {
    id: name,
    name,
    type: fromApiVarType(varType, value),
    value,
    scope: (raw.scope === 'local' ? 'local' : 'global'),
    description: typeof raw.description === 'string' ? raw.description : '',
  };
}

export async function listVariables(): Promise<VariableDef[]> {
  const data = await apiFetch('/api/variables');
  return (data.variables || []).map((v: Record<string, unknown>) => mapApiVariable(v));
}

export async function createVariable(variable: Omit<VariableDef, 'id'>): Promise<void> {
  await apiFetch('/api/variables', {
    method: 'POST',
    body: JSON.stringify({
      name: variable.name,
      value: variable.value,
      var_type: toApiVarType(variable.type),
      description: variable.description || '',
      scope: variable.scope,
    }),
  });
}

export async function updateVariableApi(name: string, updates: Partial<VariableDef>): Promise<void> {
  await apiFetch(`/api/variables/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: JSON.stringify({
      value: updates.value,
      description: updates.description,
      scope: updates.scope,
    }),
  });
}

export async function deleteVariableApi(name: string): Promise<void> {
  await apiFetch(`/api/variables/${encodeURIComponent(name)}`, { method: 'DELETE' });
}
