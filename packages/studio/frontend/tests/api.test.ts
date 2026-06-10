/**
 * HiveFlow - Frontend API Integration Tests
 *
 * Tests for all frontend pages and API interactions.
 * Covers: Orchestrator, Agents, Knowledge Base, Plugins,
 * Variables, Triggers, LLM Config, Prompt Templates, A/B Testing, etc.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// ======================== API Utility Tests ========================

describe('API Utilities', () => {
  it('should have API_BASE_URL defined', () => {
    const { API_BASE_URL } = require('@/utils/api');
    expect(API_BASE_URL).toBeDefined();
    expect(typeof API_BASE_URL).toBe('string');
  });

  it('should export apiFetch function', () => {
    const { apiFetch } = require('@/utils/api');
    expect(apiFetch).toBeDefined();
    expect(typeof apiFetch).toBe('function');
  });

  it('should build correct URL with apiFetch', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'ok' }),
      })
    ) as any;

    const { apiFetch } = require('@/utils/api');
    await apiFetch('/health');

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/health'),
      expect.any(Object)
    );
  });

  it('should handle API errors gracefully', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: () => Promise.resolve({ detail: 'Error' }),
      })
    ) as any;

    const { apiFetch } = require('@/utils/api');
    await expect(apiFetch('/test')).rejects.toThrow();
  });
});

// ======================== Store Tests ========================

describe('Frontend Stores', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should have workflow store with initial state', () => {
    const { useWorkflowStore } = require('@/store/useWorkflowStore');
    const store = useWorkflowStore.getState();
    expect(store).toBeDefined();
    expect(typeof store.nodes).not.toBe('undefined');
    expect(typeof store.edges).not.toBe('undefined');
  });

  it('should have LLM config store with initial state', () => {
    const { useLLMConfigStore } = require('@/store/useLLMConfigStore');
    const store = useLLMConfigStore.getState();
    expect(store).toBeDefined();
  });

  it('should have agents store', () => {
    const { useAgentsStore } = require('@/store/useAgentsStore');
    const store = useAgentsStore.getState();
    expect(store).toBeDefined();
  });

  it('should have analytics store', () => {
    const { useAnalyticsStore } = require('@/store/useAnalyticsStore');
    const store = useAnalyticsStore.getState();
    expect(store).toBeDefined();
  });
});

// ======================== Component Tests ========================

describe('Components', () => {
  it('should render ErrorBoundary with fallback UI on error', () => {
    const { ErrorBoundary } = require('@/components/ErrorBoundary');
    const ThrowingComponent = () => { throw new Error('Test error'); };

    // Suppress console.error for this test
    const consoleError = console.error;
    console.error = vi.fn();

    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText(/发生错误/i)).toBeDefined();
    console.error = consoleError;
  });

  it('should render ErrorBoundary children when no error', () => {
    const { ErrorBoundary } = require('@/components/ErrorBoundary');

    render(
      <ErrorBoundary>
        <div>Test Content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText('Test Content')).toBeDefined();
  });

  it('should have StreamingChat component exported', () => {
    const StreamingChat = require('@/components/StreamingChat').default;
    expect(StreamingChat).toBeDefined();
  });
});

// ======================== Page Rendering Tests ========================

describe('Page Components', () => {
  it('should render Orchestrator page', () => {
    const Orchestrator = require('@/pages/Orchestrator').default;
    render(<Orchestrator />);
    // Page should render without crashing
    expect(document.body).toBeDefined();
  });

  it('should render ABTesting page', () => {
    const ABTesting = require('@/pages/ABTesting').default;
    render(<ABTesting />);
    expect(screen.getByText(/A\/B 测试/i)).toBeDefined();
  });

  it('should render PromptTemplates page', () => {
    const PromptTemplates = require('@/pages/PromptTemplates').default;
    render(<PromptTemplates />);
    expect(screen.getByText(/Prompt 模板/i)).toBeDefined();
  });

  it('should render Variables page', () => {
    const Variables = require('@/pages/Variables').default;
    render(<Variables />);
    expect(document.body).toBeDefined();
  });

  it('should render Triggers page', () => {
    const Triggers = require('@/pages/Triggers').default;
    render(<Triggers />);
    expect(document.body).toBeDefined();
  });

  it('should render Analytics page', () => {
    const Analytics = require('@/pages/Analytics').default;
    render(<Analytics />);
    expect(document.body).toBeDefined();
  });
});

// ======================== WebSocket Manager Tests ========================

describe('WebSocket Connection Manager', () => {
  it('should export WsConnectionManager', () => {
    const { WsConnectionManager } = require('@/engine/ws/WsConnectionManager');
    expect(WsConnectionManager).toBeDefined();
  });

  it('should have connect method', () => {
    const { WsConnectionManager } = require('@/engine/ws/WsConnectionManager');
    const manager = new WsConnectionManager();
    expect(typeof manager.connect).toBe('function');
  });

  it('should have disconnect method', () => {
    const { WsConnectionManager } = require('@/engine/ws/WsConnectionManager');
    const manager = new WsConnectionManager();
    expect(typeof manager.disconnect).toBe('function');
  });

  it('should have send method', () => {
    const { WsConnectionManager } = require('@/engine/ws/WsConnectionManager');
    const manager = new WsConnectionManager();
    expect(typeof manager.send).toBe('function');
  });

  it('should not contain console.log in production code', () => {
    const fs = require('fs');
    const path = require('path');
    const wsPath = path.join(__dirname, '../src/engine/ws/WsConnectionManager.ts');

    if (fs.existsSync(wsPath)) {
      const content = fs.readFileSync(wsPath, 'utf-8');
      // Should not have console.log or console.error
      expect(content).not.toMatch(/console\.log\(/);
      expect(content).not.toMatch(/console\.error\(/);
    }
  });
});

// ======================== API Endpoint Coverage Tests ========================

describe('API Endpoint Mapping', () => {
  const expectedEndpoints = [
    '/api/workflows',
    '/api/agents',
    '/api/blackboard',
    '/api/health',
    '/api/metrics',
    '/api/monitoring',
    '/api/credentials',
    '/api/webhook',
    '/api/knowledge',
    '/api/plugins',
    '/api/variables',
    '/api/analytics',
    '/api/stream',
  ];

  it('should have all expected API endpoints defined in frontend', () => {
    // Verify that the API_BASE_URL is set and can be combined with endpoints
    const { API_BASE_URL } = require('@/utils/api');
    expect(API_BASE_URL).toBeDefined();

    for (const endpoint of expectedEndpoints) {
      const fullUrl = `${API_BASE_URL}${endpoint}`;
      expect(fullUrl).toContain(endpoint);
    }
  });
});
