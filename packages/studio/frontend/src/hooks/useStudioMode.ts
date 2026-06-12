import { useEngineStore } from '@/store/useEngineStore';
import { isMockMode, isRealMode, type StudioMode } from '@/engine/studioMode';

export function useStudioMode() {
  const mode = useEngineStore((s) => s.mode);
  const connected = useEngineStore((s) => s.connected);
  const wsError = useEngineStore((s) => s.error);

  return {
    mode: mode as StudioMode,
    isReal: isRealMode(),
    isMock: isMockMode(),
    connected,
    wsError,
    needsWs: isRealMode(),
  };
}

export { isRealMode, isMockMode, shouldUseBackendApi } from '@/engine/studioMode';
