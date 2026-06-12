/**
 * Frontend API integration and smoke tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import WsConnectionManager, { getWsManager } from '@/engine/ws/WsConnectionManager';
import { buildMenuItems } from '@/config/menuItems';
import { translate } from '@/i18n';

describe('API client', () => {
  it('defines API_BASE_URL', async () => {
    const { API_BASE_URL } = await import('@/api/client');
    expect(API_BASE_URL).toBeDefined();
    expect(typeof API_BASE_URL).toBe('string');
  });

  it('apiFetch builds correct URL', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ status: 'ok' })),
      }),
    ) as typeof fetch;

    const { apiFetch } = await import('@/api/client');
    await apiFetch('/health');

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/health'),
      expect.any(Object),
    );
  });

  it('apiFetch throws ApiError on failure', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: () => Promise.resolve({ detail: 'Error' }),
      }),
    ) as typeof fetch;

    const { apiFetch } = await import('@/api/client');
    await expect(apiFetch('/test')).rejects.toThrow();
  });
});

describe('Workflow API module', () => {
  it('exports executeWorkflow', async () => {
    const mod = await import('@/api/workflows');
    expect(typeof mod.executeWorkflow).toBe('function');
    expect(typeof mod.batchExportWorkflows).toBe('function');
  });
});

describe('Frontend stores', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('workflow store has nodes and edges', async () => {
    const { useWorkflowStore } = await import('@/store/useWorkflowStore');
    const store = useWorkflowStore.getState();
    expect(store.nodes).toBeDefined();
    expect(store.edges).toBeDefined();
  });

  it('agent runtime store has fetchRuntime', async () => {
    const { useAgentRuntimeStore } = await import('@/store/useAgentRuntimeStore');
    expect(typeof useAgentRuntimeStore.getState().fetchRuntime).toBe('function');
  });

  it('analytics store is defined', async () => {
    const { useAnalyticsStore } = await import('@/store/useAnalyticsStore');
    expect(useAnalyticsStore.getState()).toBeDefined();
  });
});

describe('WebSocket manager', () => {
  it('exports default class and getWsManager', () => {
    expect(WsConnectionManager).toBeDefined();
    expect(typeof getWsManager).toBe('function');
  });

  it('connect and disconnect are functions', () => {
    const manager = new WsConnectionManager();
    expect(typeof manager.connect).toBe('function');
    expect(typeof manager.disconnect).toBe('function');
  });
});

describe('Menu config', () => {
  it('groups advanced items', () => {
    const t = (key: Parameters<typeof translate>[1]) => translate('zh', key);
    const items = buildMenuItems(t);
    const primaryCount = items?.filter((i) => i && 'key' in i && String(i.key).startsWith('/')).length ?? 0;
    expect(primaryCount).toBeLessThanOrEqual(8);
    expect(items?.some((item) => item && 'label' in item && item.label === '高级 / 运维')).toBe(true);
  });
});
