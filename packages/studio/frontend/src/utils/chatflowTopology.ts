import type { Edge, Node } from 'reactflow';
import type { ChatflowNodeData } from '@/types';

/** Topological order of chatflow nodes (respects edges). */
export function topologicalSortChatflow(
  nodes: Node[],
  edges: Edge[],
): Node<ChatflowNodeData>[] {
  const chatNodes = nodes.filter(
    (n): n is Node<ChatflowNodeData> => n.type === 'chatflowNode',
  );
  if (chatNodes.length === 0) return [];

  const ids = new Set(chatNodes.map((n) => n.id));
  const inDegree = new Map<string, number>();
  const adj = new Map<string, string[]>();

  for (const id of ids) {
    inDegree.set(id, 0);
    adj.set(id, []);
  }

  for (const e of edges) {
    if (!ids.has(e.source) || !ids.has(e.target)) continue;
    adj.get(e.source)!.push(e.target);
    inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1);
  }

  const queue = [...ids].filter((id) => (inDegree.get(id) ?? 0) === 0);
  const order: Node<ChatflowNodeData>[] = [];

  while (queue.length > 0) {
    const id = queue.shift()!;
    const node = chatNodes.find((n) => n.id === id);
    if (node) order.push(node);
    for (const next of adj.get(id) ?? []) {
      const deg = (inDegree.get(next) ?? 1) - 1;
      inDegree.set(next, deg);
      if (deg === 0) queue.push(next);
    }
  }

  for (const n of chatNodes) {
    if (!order.some((o) => o.id === n.id)) order.push(n);
  }
  return order;
}

export interface ChatflowStepContext {
  variables: Record<string, string>;
  lastOutput: string;
  userInput: string;
}

export function buildStepQuery(
  node: Node<ChatflowNodeData>,
  ctx: ChatflowStepContext,
): string | null {
  const { nodeType, prompt, label } = node.data;
  switch (nodeType) {
    case 'user_input':
      return prompt || label || ctx.userInput || null;
    case 'ai_reply': {
      const parts = [
        prompt || label,
        ctx.lastOutput ? `Context:\n${ctx.lastOutput}` : '',
        Object.keys(ctx.variables).length
          ? `Variables: ${JSON.stringify(ctx.variables)}`
          : '',
      ].filter(Boolean);
      return parts.join('\n\n') || null;
    }
    case 'variable':
      return null;
    case 'condition':
      return prompt || `Evaluate condition: ${label}`;
    default:
      return prompt || label || null;
  }
}

export interface ChatflowStepResult {
  nodeId: string;
  nodeType: string;
  label: string;
  output: string;
  skipped?: boolean;
}

export type AgentQueryFn = (query: string) => Promise<Record<string, unknown>>;

/** Execute chatflow nodes in topological order via Agent run_query per ai_reply step. */
export async function executeChatflowWithAgent(
  nodes: Node[],
  edges: Edge[],
  runQuery: AgentQueryFn,
  initialUserInput: string = '',
): Promise<{ steps: ChatflowStepResult[]; finalAnswer: string; intentId: string }> {
  const order = topologicalSortChatflow(nodes, edges);
  const ctx: ChatflowStepContext = {
    variables: {},
    lastOutput: '',
    userInput: initialUserInput,
  };
  const steps: ChatflowStepResult[] = [];
  let intentId = '';
  let finalAnswer = '';

  for (const node of order) {
    const { nodeType, label, variable_mapping } = node.data;

    if (nodeType === 'user_input') {
      const text = node.data.prompt || ctx.userInput || label;
      ctx.userInput = text;
      ctx.lastOutput = text;
      steps.push({ nodeId: node.id, nodeType, label, output: text });
      continue;
    }

    if (nodeType === 'variable') {
      if (variable_mapping) {
        for (const [k, v] of Object.entries(variable_mapping)) {
          ctx.variables[k] = String(v);
        }
      }
      steps.push({
        nodeId: node.id,
        nodeType,
        label,
        output: JSON.stringify(ctx.variables),
        skipped: false,
      });
      continue;
    }

    if (nodeType === 'condition') {
      steps.push({
        nodeId: node.id,
        nodeType,
        label,
        output: 'condition evaluated (passthrough)',
        skipped: false,
      });
      continue;
    }

    if (nodeType === 'ai_reply') {
      const query = buildStepQuery(node, ctx);
      if (!query) {
        steps.push({ nodeId: node.id, nodeType, label, output: '', skipped: true });
        continue;
      }
      const result = await runQuery(query);
      intentId = String(result.intent_id ?? intentId);
      const answer = String(result.answer ?? JSON.stringify(result));
      ctx.lastOutput = answer;
      finalAnswer = answer;
      steps.push({ nodeId: node.id, nodeType, label, output: answer });
    }
  }

  return { steps, finalAnswer, intentId };
}
