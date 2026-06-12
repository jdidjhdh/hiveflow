import { describe, it, expect, beforeEach } from 'vitest';
import { useVariableStore } from '@/store/useVariableStore';

describe('useVariableStore', () => {
  beforeEach(() => {
    useVariableStore.getState().reset();
  });

  it('adds, updates, and deletes variables', () => {
    useVariableStore.getState().addVariable({
      name: 'api_url',
      type: 'string',
      value: 'http://localhost',
      scope: 'global',
    });
    const id = useVariableStore.getState().variables[0].id;
    expect(useVariableStore.getState().getVariableValue('api_url')).toBe('http://localhost');

    useVariableStore.getState().updateVariable(id, { value: 'http://prod' });
    expect(useVariableStore.getState().getVariableValue('api_url')).toBe('http://prod');

    useVariableStore.getState().deleteVariable(id);
    expect(useVariableStore.getState().variables).toHaveLength(0);
  });

  it('resolveReferences substitutes known variables', () => {
    useVariableStore.getState().addVariable({
      name: 'max_retries',
      type: 'number',
      value: 3,
      scope: 'global',
    });
    const out = useVariableStore.getState().resolveReferences('retry {{max_retries}} times');
    expect(out).toBe('retry 3 times');
    expect(useVariableStore.getState().resolveReferences('{{missing}}')).toBe('{{missing}}');
  });
});
