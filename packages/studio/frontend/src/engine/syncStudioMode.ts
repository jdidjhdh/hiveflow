import { useEngineStore } from '@/store/useEngineStore';
import { useLLMConfigStore } from '@/store/useLLMConfigStore';
import { useAnalyticsStore } from '@/store/useAnalyticsStore';
import { useKnowledgeBaseStore } from '@/store/useKnowledgeBaseStore';
import { useVariableStore } from '@/store/useVariableStore';
import { useTriggerStore } from '@/store/useTriggerStore';

/** Reset cached API-backed state when toggling mock ↔ real. */
export async function applyStudioModeChange(mode: 'mock' | 'real'): Promise<void> {
  useLLMConfigStore.getState().reset();
  useAnalyticsStore.getState().reset();
  useKnowledgeBaseStore.getState().reset();
  useVariableStore.getState().reset();
  useTriggerStore.getState().reset();

  const { connect, switchToMock } = useEngineStore.getState();
  if (mode === 'real') {
    await connect();
  } else {
    switchToMock();
  }
}
