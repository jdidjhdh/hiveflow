import { create } from 'zustand';
import type { TriggerDef } from '@/types';

interface TriggerState {
  triggers: TriggerDef[];
  addTrigger: (trigger: Omit<TriggerDef, 'id'>) => void;
  updateTrigger: (id: string, updates: Partial<TriggerDef>) => void;
  deleteTrigger: (id: string) => void;
  toggleTrigger: (id: string) => void;
  reset: () => void;
}

let nextTriggerId = 1;

export const useTriggerStore = create<TriggerState>((set) => ({
  triggers: [],

  addTrigger: (trigger) => {
    const newTrigger: TriggerDef = {
      ...trigger,
      id: `trigger_${nextTriggerId++}`,
      created_at: Date.now(),
      enabled: trigger.enabled ?? true,
    };
    set((s) => ({ triggers: [...s.triggers, newTrigger] }));
  },

  updateTrigger: (id, updates) => {
    set((s) => ({
      triggers: s.triggers.map((t) => (t.id === id ? { ...t, ...updates } : t)),
    }));
  },

  deleteTrigger: (id) => {
    set((s) => ({
      triggers: s.triggers.filter((t) => t.id !== id),
    }));
  },

  toggleTrigger: (id) => {
    set((s) => ({
      triggers: s.triggers.map((t) =>
        t.id === id ? { ...t, enabled: !t.enabled } : t
      ),
    }));
  },

  reset: () => {
    set({ triggers: [] });
    nextTriggerId = 1;
  },
}));
