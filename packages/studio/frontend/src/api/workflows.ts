import { apiFetch } from './client';

export interface WorkflowExecuteResponse {
  wf_id: string;
  status: string;
  result?: {
    status?: string;
    results?: Record<string, unknown>;
    error?: string;
  };
  results?: Record<string, unknown>;
}

export async function executeWorkflow(
  graph: Record<string, unknown>,
): Promise<WorkflowExecuteResponse> {
  return apiFetch('/api/workflows/execute', {
    method: 'POST',
    body: JSON.stringify({ graph }),
  });
}

export async function stopWorkflow(wfId: string): Promise<{ wf_id: string; status: string }> {
  return apiFetch(`/api/workflows/${wfId}/stop`, { method: 'POST' });
}

export async function batchExportWorkflows(): Promise<{ count: number; workflows: unknown[] }> {
  return apiFetch('/api/workflows/batch-export', { method: 'POST' });
}
