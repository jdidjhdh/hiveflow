import { create } from 'zustand';
import type { VariableDef } from '@/types';

interface VariableState {
  variables: VariableDef[];
  addVariable: (variable: Omit<VariableDef, 'id'>) => void;
  updateVariable: (id: string, updates: Partial<VariableDef>) => void;
  deleteVariable: (id: string) => void;
  getVariableValue: (name: string) => unknown;
  resolveReferences: (template: string) => string;
  reset: () => void;
}

let nextId = 1;

export const useVariableStore = create<VariableState>((set, get) => ({
  variables: [],

  addVariable: (variable) => {
    const newVar: VariableDef = {
      ...variable,
      id: `var_${nextId++}`,
    };
    set((s) => ({ variables: [...s.variables, newVar] }));
  },

  updateVariable: (id, updates) => {
    set((s) => ({
      variables: s.variables.map((v) => (v.id === id ? { ...v, ...updates } : v)),
    }));
  },

  deleteVariable: (id) => {
    set((s) => ({
      variables: s.variables.filter((v) => v.id !== id),
    }));
  },

  getVariableValue: (name) => {
    const { variables } = get();
    const found = variables.find((v) => v.name === name);
    return found?.value;
  },

  resolveReferences: (template: string) => {
    const { variables } = get();
    return template.replace(/\{\{([^}]+)\}\}/g, (_match, name) => {
      const trimmed = name.trim();
      const found = variables.find((v) => v.name === trimmed);
      if (found === undefined) return `{{${name}}}`;
      if (found.value === undefined) return `{{${name}}}`;
      return String(found.value);
    });
  },

  reset: () => {
    set({ variables: [] });
    nextId = 1;
  },
}));
