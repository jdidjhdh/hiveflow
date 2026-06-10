import { create } from 'zustand';
import type { EventRecord, ECM } from '@/types';

interface EventState {
  events: EventRecord[];
  paused: boolean;
  filters: { topic?: string; agent?: string };
  addEvent: (topic: string, data: ECM) => void;
  setPaused: (paused: boolean) => void;
  setFilters: (filters: Partial<EventState['filters']>) => void;
  clear: () => void;
}

export const useEventStore = create<EventState>((set) => ({
  events: [],
  paused: false,
  filters: {},

  addEvent: (topic, data) => set((s) => {
    if (s.paused) return s;
    const record: EventRecord = { timestamp: Date.now() / 1000, topic, data };
    return { events: [...s.events.slice(-999), record] };
  }),

  setPaused: (paused) => set({ paused }),
  setFilters: (filters) => set((s) => ({
    filters: { ...s.filters, ...filters },
  })),
  clear: () => set({ events: [] }),
}));