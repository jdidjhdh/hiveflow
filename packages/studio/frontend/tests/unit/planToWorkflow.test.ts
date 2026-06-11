import { describe, it, expect } from 'vitest';
import { planToReactFlow } from '@/utils/planToWorkflow';

describe('planToReactFlow', () => {
  it('maps nodes and dependency edges', () => {
    const plan = {
      general_step: { task: 'general', depends_on: [] },
      final_answer: { task: 'summarize', depends_on: ['general_step'] },
    };
    const { nodes, edges } = planToReactFlow(plan);
    expect(nodes).toHaveLength(2);
    expect(nodes.find((n) => n.id === 'general_step')?.data.task).toBe('general');
    expect(edges).toHaveLength(1);
    expect(edges[0].source).toBe('general_step');
    expect(edges[0].target).toBe('final_answer');
  });

  it('returns empty for empty plan', () => {
    const { nodes, edges } = planToReactFlow({});
    expect(nodes).toHaveLength(0);
    expect(edges).toHaveLength(0);
  });
});
