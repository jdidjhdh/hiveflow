import { describe, it, expect, vi } from 'vitest';
import { topologicalSortChatflow, executeChatflowWithAgent } from '@/utils/chatflowTopology';
import type { Node, Edge } from 'reactflow';
import type { ChatflowNodeData } from '@/types';

describe('chatflowTopology', () => {
  it('sorts nodes by edges', () => {
    const nodes: Node<ChatflowNodeData>[] = [
      { id: 'a', type: 'chatflowNode', position: { x: 0, y: 0 }, data: { label: 'A', nodeType: 'user_input', prompt: 'hi' } },
      { id: 'b', type: 'chatflowNode', position: { x: 0, y: 100 }, data: { label: 'B', nodeType: 'ai_reply', prompt: 'reply' } },
    ];
    const edges: Edge[] = [{ id: 'e1', source: 'a', target: 'b' }];
    const order = topologicalSortChatflow(nodes, edges);
    expect(order.map((n) => n.id)).toEqual(['a', 'b']);
  });

  it('executes ai_reply steps in order', async () => {
    const nodes: Node<ChatflowNodeData>[] = [
      { id: 'in', type: 'chatflowNode', position: { x: 0, y: 0 }, data: { label: 'In', nodeType: 'user_input', prompt: 'question' } },
      { id: 'out', type: 'chatflowNode', position: { x: 0, y: 80 }, data: { label: 'Out', nodeType: 'ai_reply', prompt: 'answer' } },
    ];
    const edges: Edge[] = [{ id: 'e1', source: 'in', target: 'out' }];
    const runQuery = vi.fn().mockResolvedValue({ answer: 'ok', intent_id: 'i1' });
    const result = await executeChatflowWithAgent(nodes, edges, runQuery, 'hello');
    expect(runQuery).toHaveBeenCalledTimes(1);
    expect(result.steps).toHaveLength(2);
    expect(result.finalAnswer).toBe('ok');
  });
});
