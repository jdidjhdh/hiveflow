import { describe, it, expect } from 'vitest';
import { agentColor, SKILL_COLORS } from '@/components/agents/agentConstants';
import type { Capability } from '@/types';

describe('agentConstants', () => {
  it('agentColor uses first skill or default', () => {
    const agent = {
      agent_id: 'a',
      skills: ['search'],
    } as Capability;
    expect(agentColor(agent)).toBe(SKILL_COLORS.search);
    expect(agentColor({ ...agent, skills: [] })).toBe('#6366f1');
  });
});
