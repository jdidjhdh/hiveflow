import { create } from 'zustand';
import { MockEngine, type IEngine } from '@/engine/mock/MockEngine';
import { getWsManager, resetWsManager } from '@/engine/ws/WsConnectionManager';

interface EngineState {
  mode: 'mock' | 'real';
  connected: boolean;
  error: string | null;
  engine: IEngine | null;
  setMode: (mode: 'mock' | 'real') => void;
  connect: (url?: string) => Promise<void>;
  disconnect: () => void;
  getEngine: () => IEngine;
}

// 单例引擎实例
let engineInstance: IEngine | null = null;

function getOrCreateEngine(): IEngine {
  if (!engineInstance) {
    engineInstance = new MockEngine();
  }
  return engineInstance;
}

export const useEngineStore = create<EngineState>((set, get) => ({
  mode: 'mock',
  connected: false,
  error: null,
  engine: getOrCreateEngine(),

  setMode: (mode) => set({ mode, error: null }),

  connect: async (url) => {
    if (url) {
      set({ mode: 'real', error: null });
      try {
        const wsManager = getWsManager(url);
        const success = await wsManager.connect();
        if (success) {
          wsManager.subscribeToEngine();
          set({ connected: true, error: null });
        } else {
          set({ connected: false, error: 'WebSocket 连接失败' });
        }
      } catch (e) {
        set({ connected: false, error: String(e) });
      }
    } else {
      resetWsManager();
      set({ mode: 'mock', connected: true, engine: getOrCreateEngine() });
    }
  },

  disconnect: () => {
    resetWsManager();
    set({ connected: false });
  },

  getEngine: () => {
    const state = get();
    if (!state.engine) {
      const engine = getOrCreateEngine();
      set({ engine });
      return engine;
    }
    return state.engine;
  },
}));