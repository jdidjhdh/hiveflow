import { useCallback, useRef, useState, useEffect, useMemo, createElement } from 'react';

import { useNodesState, useEdgesState, addEdge, Connection, Node } from 'reactflow';

import type { MenuProps } from 'antd';

import { App } from 'antd';

import { useI18n } from '@/i18n';

import { useWorkflowStore } from '@/store/useWorkflowStore';

import { useEngineStore } from '@/store/useEngineStore';

import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';

import type { WorkflowNodeData } from '@/types';

import { getErrorMessage } from '@/api/client';

import { batchExportWorkflows as batchExportWorkflowsApi } from '@/api/workflows';

import { getBuiltinTemplates, templateData } from '@/components/orchestrator/constants/templates';

import { getNodeTypeConfigs, type NodeTypeConfig, buildDefaultNodeData } from '@/components/orchestrator/constants/nodeTypeConfigs';

import { useWorkflowExecution } from '@/components/orchestrator/hooks/useWorkflowExecution';

import { useAgentPlanImport } from '@/components/orchestrator/hooks/useAgentPlanImport';



export function useOrchestratorPage() {

  const { t } = useI18n();

  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  const [reactFlowInstance, setReactFlowInstance] = useState<{ screenToFlowPosition: (p: { x: number; y: number }) => { x: number; y: number } } | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowNodeData>([]);

  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const [selectedNode, setSelectedNode] = useState<Node<WorkflowNodeData> | null>(null);

  const [drawerOpen, setDrawerOpen] = useState(false);

  const nodesRef = useRef(nodes);

  nodesRef.current = nodes;

  /** Prevents async IndexedDB hydration from overwriting in-flight canvas edits. */
  const skipPersistedHydrationRef = useRef(false);

  const pendingCanvasEditsRef = useRef(0);

  const [canvasHydrated, setCanvasHydrated] = useState(false);

  const markCanvasTouched = useCallback(() => {
    skipPersistedHydrationRef.current = true;
    pendingCanvasEditsRef.current += 1;
  }, []);



  const { message } = App.useApp();

  const engineMode = useEngineStore((s) => s.mode);

  const runtimeMode = useAgentRuntimeStore((s) => s.runtimeMode);

  const runtimeSkills = useAgentRuntimeStore((s) => s.skills);

  const runtimeLoading = useAgentRuntimeStore((s) => s.loading);

  const fetchRuntime = useAgentRuntimeStore((s) => s.fetchRuntime);

  const setRuntimeMode = useAgentRuntimeStore((s) => s.setRuntimeMode);

  const executionStatus = useWorkflowStore((s) => s.executionStatus);



  const nodeTypeConfigs = useMemo(() => getNodeTypeConfigs(t), [t]);



  useEffect(() => {

    if (engineMode === 'real') {

      fetchRuntime();

    }

  }, [engineMode, fetchRuntime]);



  useEffect(() => {

    let cancelled = false;

    const loadPersistedWorkflow = async () => {

      try {

        const idbReady = (window as unknown as { __HF_IDB_READY__?: Promise<boolean> }).__HF_IDB_READY__;

        if (idbReady) {

          await idbReady;

        }

        const workflows = await useWorkflowStore.getState().listWorkflows();

        if (workflows.length > 0) {

          const latest = workflows.sort((a, b) => b.updatedAt - a.updatedAt)[0];

          await useWorkflowStore.getState().loadFromIndexedDB(latest.id);

          const state = useWorkflowStore.getState();

          if (
            !cancelled
            && !skipPersistedHydrationRef.current
            && pendingCanvasEditsRef.current === 0
            && nodesRef.current.length === 0
            && state.nodes.length > 0
          ) {

            setNodes(state.nodes);

            setEdges(state.edges);

          }

        }

      } catch {

        // 首次访问或加载失败，使用空画布

      } finally {

        if (!cancelled) {

          setCanvasHydrated(true);

        }

      }

    };

    loadPersistedWorkflow();

    return () => {

      cancelled = true;

    };

    // Hydrate once on mount; setNodes/setEdges are stable but omitting deps avoids re-entry races.

    // eslint-disable-next-line react-hooks/exhaustive-deps

  }, []);



  const pushToStore = useCallback(() => {

    useWorkflowStore.setState({ nodes, edges });

    setTimeout(() => useWorkflowStore.getState().saveToIndexedDB(), 0);

  }, [nodes, edges]);



  const {

    runWorkflowExecution,

    stopExecution,

    executionProgress,

  } = useWorkflowExecution({

    nodes,

    nodesRef,

    setNodes,

    setEdges,

    pushToStore,

    engineMode,

  });



  const agentPlan = useAgentPlanImport({ nodes, setNodes, setEdges });



  const onConnect = useCallback((params: Connection) => {

    const edge = { ...params, id: `e-${params.source}-${params.target}`, type: 'deletable' };

    setEdges((eds) => addEdge(edge, eds));

  }, [setEdges]);



  const onDragOver = useCallback((event: React.DragEvent) => {

    event.preventDefault();

    event.dataTransfer.dropEffect = 'move';

  }, []);



  const appendNodeFromConfig = useCallback(
    (cfg: NodeTypeConfig) => {
      markCanvasTouched();

      const fallbackPosition = { x: 250, y: 200 };
      let position = fallbackPosition;

      if (reactFlowInstance && reactFlowWrapper.current) {
        const rect = reactFlowWrapper.current.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          const center = reactFlowInstance.screenToFlowPosition({
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
          });
          if (Number.isFinite(center.x) && Number.isFinite(center.y)) {
            position = { x: center.x - 75, y: center.y - 20 };
          }
        }
      }

      setNodes((nds) => [
        ...nds,
        {
          id: `node_${Date.now()}`,
          type: cfg.type,
          position,
          data: buildDefaultNodeData(t, cfg.variant, cfg.label),
        },
      ]);
    },
    [reactFlowInstance, setNodes, t, markCanvasTouched],
  );



  const onNodePanelDoubleClick = useCallback(
    (cfg: NodeTypeConfig) => {
      appendNodeFromConfig(cfg);
    },
    [appendNodeFromConfig],
  );



  const onDrop = useCallback(

    (event: React.DragEvent) => {

      event.preventDefault();

      markCanvasTouched();

      const type = event.dataTransfer.getData('application/reactflow-type');

      const label = event.dataTransfer.getData('application/reactflow-label');

      const variant = event.dataTransfer.getData('application/reactflow-variant') || 'task';

      if (!type || !reactFlowInstance) return;



      const position = reactFlowInstance.screenToFlowPosition({

        x: event.clientX,

        y: event.clientY,

      });



      setNodes((nds) => [

        ...nds,

        {

          id: `node_${Date.now()}`,

          type,

          position,

          data: buildDefaultNodeData(t, variant as WorkflowNodeData['variant'], label || t('orchestrator.defaults.newTask')),

        },

      ]);

    },

    [reactFlowInstance, setNodes, t, markCanvasTouched],

  );



  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {

    setSelectedNode(node);

    setDrawerOpen(true);

  }, []);



  const saveNodeConfig = useCallback((values: Record<string, unknown>) => {

    if (!selectedNode) return;

    setNodes((nds) =>

      nds.map((n) =>

        n.id === selectedNode.id

          ? {

              ...n,

              data: {

                ...n.data,

                label: values.label as string,

                task: values.task as string,

                skills: (values.skills as string[]) || [],

                retry_policy: values.max_attempts ? {

                  max_attempts: values.max_attempts as number,

                  backoff_type: ((values.backoff_type as string) || 'constant') as 'constant' | 'exponential',

                  backoff_base: (values.backoff_base as number) || 1,

                  max_backoff: (values.max_backoff as number) || 30,

                } : undefined,

                on_failure: values.on_failure as WorkflowNodeData['on_failure'],

                expectation: values.state_key ? {

                  state_key: values.state_key as string,

                  expected_schema: {},

                  validation: (values.validation as string) || '',

                  deadline: (values.deadline as number) || 30,

                  use_json_schema: false,

                } : undefined,

                ...(n.data.variant === 'condition' && values.branches ? {

                  condition_data: {

                    condition: (values.condition as string) || '',

                    branches: values.branches,

                    default_branch: values.default_branch as string,

                  },

                } : {}),

                ...(n.data.variant === 'code' ? {

                  code_data: {

                    language: (values.language as 'javascript' | 'python') || 'javascript',

                    code: (values.code as string) || '',

                    input_mapping: (values.input_mapping as Record<string, string>) || {},

                    output_mapping: (values.output_mapping as Record<string, string>) || {},

                  },

                } : {}),

                ...(n.data.variant === 'hitl' ? {

                  hitl_config: {

                    prompt: (values.hitl_prompt as string) || t('orchestrator.defaults.hitlPrompt'),

                    action: (values.hitl_action as 'approval' | 'review' | 'input') || 'approval',

                    timeout_seconds: (values.hitl_timeout as number) || 300,

                    on_timeout: (values.hitl_on_timeout as 'fail' | 'approve' | 'skip') || 'fail',

                  },

                } : {}),

              },

            }

          : n,

      ),

    );

    setDrawerOpen(false);

    message.success(t('orchestrator.messages.nodeSaved'));

  }, [selectedNode, setNodes, message, t]);



  const deleteSelectedNode = useCallback(() => {

    if (!selectedNode) return;

    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));

    setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));

    setDrawerOpen(false);

  }, [selectedNode, setNodes, setEdges]);



  const handleRuntimeToggle = useCallback(async (checked: boolean) => {

    try {

      await setRuntimeMode(checked ? 'agent' : 'core');

      message.success(checked ? t('orchestrator.messages.runtimeAgent') : t('orchestrator.messages.runtimeCore'));

    } catch (e) {

      message.error(getErrorMessage(e));

    }

  }, [setRuntimeMode, message, t]);



  const exportWorkflow = useCallback(() => {

    pushToStore();

    const data = useWorkflowStore.getState().exportWorkflow();

    const exportData = {

      format: 'hflow/v1',

      exported_at: new Date().toISOString(),

      nodes: data.nodes,

      edges: data.edges,

    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });

    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');

    a.href = url;

    a.download = 'workflow.hflow';

    a.click();

    URL.revokeObjectURL(url);

    message.success(t('orchestrator.messages.exported'));

  }, [pushToStore, message, t]);



  const importWorkflow = useCallback(() => {

    const input = document.createElement('input');

    input.type = 'file';

    input.accept = '.hflow,.json';

    input.onchange = (e) => {

      const file = (e.target as HTMLInputElement).files?.[0];

      if (!file) return;

      const reader = new FileReader();

      reader.onload = () => {

        try {

          const data = JSON.parse(reader.result as string);

          if (data.nodes && data.edges) {

            markCanvasTouched();

            setNodes(data.nodes);

            setEdges(data.edges);

            useWorkflowStore.getState().loadWorkflow(data);

            message.success(t('orchestrator.messages.imported'));

          } else {

            message.error(t('orchestrator.messages.invalidWorkflow'));

          }

        } catch {

          message.error(t('orchestrator.messages.invalidWorkflow'));

        }

      };

      reader.readAsText(file);

    };

    input.click();

  }, [setNodes, setEdges, message, t, markCanvasTouched]);



  const runBatchExport = useCallback(async () => {

    if (useEngineStore.getState().mode !== 'real') {

      message.warning(t('orchestrator.messages.batchExportRealMode'));

      return;

    }

    try {

      const data = await batchExportWorkflowsApi();

      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });

      const url = URL.createObjectURL(blob);

      const a = document.createElement('a');

      a.href = url;

      a.download = 'workflows_batch.hflow';

      a.click();

      URL.revokeObjectURL(url);

      message.success(t('orchestrator.messages.batchExported', { count: data.count }));

    } catch {

      message.error(t('orchestrator.messages.batchExportFailed'));

    }

  }, [message, t]);



  const autoLayout = useCallback(() => {

    setNodes((nds) => {

      if (nds.length === 0) return nds;

      const cols = Math.ceil(Math.sqrt(nds.length));

      return nds.map((n, i) => ({

        ...n,

        position: { x: (i % cols) * 220 + 50, y: Math.floor(i / cols) * 120 + 50 },

      }));

    });

  }, [setNodes]);



  const newCanvas = useCallback(() => {

    markCanvasTouched();

    setNodes([]);

    setEdges([]);

    useWorkflowStore.getState().reset();

    message.success(t('orchestrator.messages.newCanvas'));

  }, [setNodes, setEdges, message, t, markCanvasTouched]);



  const saveWorkflow = useCallback(() => {

    pushToStore();

    message.success(t('orchestrator.messages.workflowSaved'));

  }, [pushToStore, message, t]);



  const loadTemplate = useCallback((key: string) => {

    markCanvasTouched();

    const tmpl = templateData[key];

    if (!tmpl) return;

    setNodes(tmpl.nodes);

    setEdges(tmpl.edges);

    useWorkflowStore.getState().loadWorkflow(tmpl);

    const label = getBuiltinTemplates(t).find((item) => item.key === key)?.label ?? key;

    message.success(t('orchestrator.templates.loaded', { name: label }));

  }, [setNodes, setEdges, message, t, markCanvasTouched]);



  const templateMenuItems: MenuProps['items'] = useMemo(

    () => getBuiltinTemplates(t).map((item) => ({

      key: item.key,

      label: createElement('span', { 'data-testid': `template-${item.key}` }, item.label),

      title: item.description,

    })),

    [t],

  );



  const exportCanvasAsLangGraph = useCallback(() => {

    void agentPlan.exportCanvasAsLangGraph(pushToStore);

  }, [agentPlan, pushToStore]);



  return {

    reactFlowWrapper,

    nodes,

    edges,

    onNodesChange,

    onEdgesChange,

    selectedNode,

    drawerOpen,

    setDrawerOpen,

    agentDrawerOpen: agentPlan.agentDrawerOpen,

    setAgentDrawerOpen: agentPlan.setAgentDrawerOpen,

    agentQuery: agentPlan.agentQuery,

    setAgentQuery: agentPlan.setAgentQuery,

    agentLoading: agentPlan.agentLoading,

    agentResult: agentPlan.agentResult,

    engineMode,

    runtimeMode,

    runtimeSkills,

    runtimeLoading,

    executionStatus,

    executionProgress,

    templateMenuItems,

    nodeTypeConfigs,

    onConnect,

    onDragOver,

    onDrop,

    canvasHydrated,

    onAddNodeFromLibrary: appendNodeFromConfig,

    onNodePanelDoubleClick: appendNodeFromConfig,

    onNodeClick,

    saveNodeConfig,

    deleteSelectedNode,

    runWorkflowExecution,

    stopExecution,

    newCanvas,

    saveWorkflow,

    importWorkflow,

    exportWorkflow,

    exportCanvasAsLangGraph,

    runBatchExport,

    autoLayout,

    loadTemplate,

    handleRuntimeToggle,

    handleAgentQuery: agentPlan.handleAgentQuery,

    handlePlanOnly: agentPlan.handlePlanOnly,

    importPlanToCanvas: agentPlan.importPlanToCanvas,

    exportAgentPlanAsLangGraph: agentPlan.exportAgentPlanAsLangGraph,

    setReactFlowInstance,

  };

}


