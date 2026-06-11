import type { Edge, Node } from 'reactflow';
import type { WorkflowNodeData } from '@/types';

export interface TaskGraphNodeDef {
  task: string;
  depends_on?: string[];
  [key: string]: unknown;
}

export type TaskGraphPlan = Record<string, TaskGraphNodeDef>;

function computeLayers(plan: TaskGraphPlan): Record<string, number> {
  const layers: Record<string, number> = {};

  function depth(name: string, visiting: Set<string>): number {
    if (layers[name] !== undefined) return layers[name];
    if (visiting.has(name)) return 0;
    visiting.add(name);
    const deps = plan[name]?.depends_on ?? [];
    const d =
      deps.length === 0
        ? 0
        : 1 + Math.max(...deps.map((dep) => depth(dep, visiting)));
    layers[name] = d;
    visiting.delete(name);
    return d;
  }

  for (const name of Object.keys(plan)) {
    depth(name, new Set());
  }
  return layers;
}

/** Map HiveMind TaskGraph JSON to Orchestrator ReactFlow nodes and edges. */
export function planToReactFlow(plan: TaskGraphPlan): {
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
} {
  const nodeNames = Object.keys(plan);
  if (nodeNames.length === 0) {
    return { nodes: [], edges: [] };
  }

  const layers = computeLayers(plan);
  const colWidth = 220;
  const rowHeight = 120;

  const nodes: Node<WorkflowNodeData>[] = nodeNames.map((name) => {
    const def = plan[name];
    const layer = layers[name] ?? 0;
    const sameLayer = nodeNames.filter((n) => (layers[n] ?? 0) === layer);
    const posInLayer = sameLayer.indexOf(name);
    const task = def.task || name;

    return {
      id: name,
      type: 'taskNode',
      position: { x: 80 + posInLayer * colWidth, y: 40 + layer * rowHeight },
      data: {
        label: name === 'final_answer' ? '最终回答' : name,
        task,
        skills: [task],
        variant: name === 'final_answer' ? 'subgraph' : 'task',
        status: 'idle',
        on_failure: 'abort',
      },
    };
  });

  const edges: Edge[] = [];
  for (const [name, def] of Object.entries(plan)) {
    for (const dep of def.depends_on ?? []) {
      if (!plan[dep]) continue;
      edges.push({
        id: `e-${dep}-${name}`,
        source: dep,
        target: name,
        type: 'deletable',
      });
    }
  }

  return { nodes, edges };
}
