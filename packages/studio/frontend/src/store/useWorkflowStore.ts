import { create } from 'zustand';
import type { Node, Edge } from 'reactflow';
import type { TaskGraph, WorkflowNodeData } from '@/types';
import dbManager from '@/persistence/IndexedDBManager';

// 当前工作流 ID（用于 IndexedDB 持久化）
let currentWorkflowId = 'default';

interface WorkflowState {
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
  executionId: string | null;
  executionStatus: 'idle' | 'running' | 'completed' | 'failed';
  nodeResults: Record<string, unknown>;
  currentWorkflowId: string;
  addNode: (node: Node<WorkflowNodeData>) => void;
  removeNode: (id: string) => void;
  addEdge: (edge: Edge) => void;
  removeEdge: (id: string) => void;
  setNodes: (nodes: Node<WorkflowNodeData>[]) => void;
  setEdges: (edges: Edge[]) => void;
  setExecutionStatus: (status: WorkflowState['executionStatus']) => void;
  setNodeResult: (nodeId: string, result: unknown) => void;
  updateNodeStatus: (nodeId: string, status: WorkflowNodeData['status'], result?: unknown, error?: string) => void;
  loadWorkflow: (json: { nodes: Node<WorkflowNodeData>[]; edges: Edge[] }, id?: string) => void;
  exportWorkflow: () => { nodes: Node<WorkflowNodeData>[]; edges: Edge[]; graph: TaskGraph };
  reset: () => void;
  loadFromIndexedDB: (id: string) => Promise<void>;
  saveToIndexedDB: () => Promise<void>;
  listWorkflows: () => Promise<{ id: string; name: string; updatedAt: number }[]>;
  deleteWorkflow: (id: string) => Promise<void>;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  nodes: [],
  edges: [],
  executionId: null,
  executionStatus: 'idle',
  nodeResults: {},
  currentWorkflowId: 'default',

  addNode: (node) => {
    set((s) => ({ nodes: [...s.nodes, node] }));
    // 自动保存到 IndexedDB
    setTimeout(() => get().saveToIndexedDB(), 0);
  },
  removeNode: (id) => {
    set((s) => ({
      nodes: s.nodes.filter(n => n.id !== id),
      edges: s.edges.filter(e => e.source !== id && e.target !== id),
    }));
    setTimeout(() => get().saveToIndexedDB(), 0);
  },
  addEdge: (edge) => {
    set((s) => ({ edges: [...s.edges, edge] }));
    setTimeout(() => get().saveToIndexedDB(), 0);
  },
  removeEdge: (id) => {
    set((s) => ({ edges: s.edges.filter(e => e.id !== id) }));
    setTimeout(() => get().saveToIndexedDB(), 0);
  },
  setNodes: (nodes) => {
    set({ nodes });
    setTimeout(() => get().saveToIndexedDB(), 0);
  },
  setEdges: (edges) => {
    set({ edges });
    setTimeout(() => get().saveToIndexedDB(), 0);
  },
  setExecutionStatus: (status) => set({ executionStatus: status }),
  setNodeResult: (nodeId, result) => set((s) => ({
    nodeResults: { ...s.nodeResults, [nodeId]: result },
  })),

  updateNodeStatus: (nodeId, status, result?, error?) => set((s) => ({
    nodes: s.nodes.map(n =>
      n.id === nodeId
        ? { ...n, data: { ...n.data, status, result, error } }
        : n
    ),
    nodeResults: result !== undefined ? { ...s.nodeResults, [nodeId]: result } : s.nodeResults,
  })),

  loadWorkflow: (json, id?) => {
    const workflowId = id || `wf_${Date.now()}`;
    currentWorkflowId = workflowId;
    set({
      nodes: json.nodes,
      edges: json.edges,
      executionStatus: 'idle',
      nodeResults: {},
      currentWorkflowId: workflowId,
    });
  },

  exportWorkflow: () => {
    const { nodes, edges } = get();
    const graph: TaskGraph = {};
    nodes.forEach(n => {
      if (n.type === 'startNode' || n.type === 'endNode') return;
      graph[n.id] = {
        task: n.data.task || n.data.label,
        depends_on: edges.filter(e => e.target === n.id).map(e => e.source),
        retry_policy: n.data.retry_policy,
        on_failure: n.data.on_failure,
        dynamic: n.data.dynamic,
        expectation: n.data.expectation,
        required_skills: n.data.skills,
      };
    });
    return { nodes, edges, graph };
  },

  reset: () => {
    currentWorkflowId = `wf_${Date.now()}`;
    set({
      nodes: [],
      edges: [],
      executionId: null,
      executionStatus: 'idle',
      nodeResults: {},
      currentWorkflowId,
    });
  },

  // IndexedDB 持久化
  loadFromIndexedDB: async (id: string) => {
    try {
      const doc = await dbManager.getWorkflow(id);
      if (doc) {
        currentWorkflowId = id;
        set({
          nodes: doc.nodes,
          edges: doc.edges,
          executionStatus: 'idle',
          nodeResults: {},
          currentWorkflowId: id,
        });
      }
    } catch (e) {
      console.error('Failed to load from IndexedDB:', e);
    }
  },

  saveToIndexedDB: async () => {
    try {
      const { nodes, edges, currentWorkflowId: wfId } = get();
      await dbManager.saveWorkflow({
        id: wfId,
        name: `工作流 ${wfId.slice(-6)}`,
        nodes,
        edges,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      });
    } catch (e) {
      console.error('Failed to save to IndexedDB:', e);
    }
  },

  listWorkflows: async () => {
    try {
      const workflows = await dbManager.getAllWorkflows();
      return workflows.map(w => ({
        id: w.id,
        name: w.name,
        updatedAt: w.updatedAt,
      }));
    } catch (e) {
      console.error('Failed to list workflows:', e);
      return [];
    }
  },

  deleteWorkflow: async (id: string) => {
    try {
      await dbManager.deleteWorkflow(id);
    } catch (e) {
      console.error('Failed to delete workflow:', e);
    }
  },
}));