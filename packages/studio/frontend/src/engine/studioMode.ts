/**
 * Unified Studio engine mode helpers for stores and components.
 */
import { useEngineStore } from '@/store/useEngineStore';

export type StudioMode = 'mock' | 'real';

export const STUDIO_MODE_STORAGE_KEY = 'hf_engine_mode';

export function getStudioMode(): StudioMode {
  return useEngineStore.getState().mode;
}

export function isRealMode(): boolean {
  return getStudioMode() === 'real';
}

export function isMockMode(): boolean {
  return getStudioMode() === 'mock';
}

export function shouldUseBackendApi(): boolean {
  return isRealMode();
}
