import { useCallback, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { Edge, Node } from 'reactflow';
import { App, Modal } from 'antd';
import { useI18n } from '@/i18n';
import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { planToReactFlow, type TaskGraphPlan } from '@/utils/planToWorkflow';
import { downloadJson, downloadText } from '@/utils/downloadFile';
import { getErrorMessage } from '@/api/client';
import type { WorkflowNodeData } from '@/types';

interface UseAgentPlanImportParams {
  nodes: Node<WorkflowNodeData>[];
  setNodes: Dispatch<SetStateAction<Node<WorkflowNodeData>[]>>;
  setEdges: Dispatch<SetStateAction<Edge[]>>;
}

export function useAgentPlanImport({ nodes, setNodes, setEdges }: UseAgentPlanImportParams) {
  const { t } = useI18n();
  const { message } = App.useApp();
  const runAgentQuery = useAgentRuntimeStore((s) => s.runQuery);
  const planOnly = useAgentRuntimeStore((s) => s.planOnly);
  const exportLangGraph = useAgentRuntimeStore((s) => s.exportLangGraph);

  const [agentDrawerOpen, setAgentDrawerOpen] = useState(false);
  const [agentQuery, setAgentQuery] = useState('');
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentResult, setAgentResult] = useState<Record<string, unknown> | null>(null);

  const exportPlanAsLangGraph = useCallback(async (
    plan: Record<string, unknown>,
    source: 'plan' | 'canvas',
    includePython = false,
    intentId?: string,
  ) => {
    try {
      const wfId = source === 'canvas'
        ? useWorkflowStore.getState().currentWorkflowId
        : String(intentId ?? 'studio_plan');
      const result = await exportLangGraph(plan, {
        workflowId: wfId,
        includePython,
      });
      downloadJson(result.spec, `langgraph-${wfId}.json`);
      if (includePython && result.python) {
        downloadText(result.python, `langgraph-${wfId}.py`, 'text/x-python');
      }
      message.success(t('orchestrator.messages.langGraphExported', { count: result.node_count }));
    } catch (e) {
      message.error(getErrorMessage(e));
    }
  }, [exportLangGraph, message, t]);

  const handleAgentQuery = useCallback(async () => {
    if (!agentQuery.trim()) return;
    setAgentLoading(true);
    try {
      const result = await runAgentQuery(agentQuery);
      setAgentResult(result);
      message.success(t('orchestrator.messages.agentQueryDone'));
    } catch (e) {
      message.error(getErrorMessage(e));
    } finally {
      setAgentLoading(false);
    }
  }, [agentQuery, runAgentQuery, message, t]);

  const handlePlanOnly = useCallback(async () => {
    if (!agentQuery.trim()) return;
    setAgentLoading(true);
    try {
      const result = await planOnly(agentQuery);
      setAgentResult(result);
      message.success(t('orchestrator.messages.planGenerated'));
    } catch (e) {
      message.error(getErrorMessage(e));
    } finally {
      setAgentLoading(false);
    }
  }, [agentQuery, planOnly, message, t]);

  const importPlanToCanvas = useCallback((plan: Record<string, unknown>) => {
    const doImport = () => {
      const { nodes: flowNodes, edges: flowEdges } = planToReactFlow(plan as TaskGraphPlan);
      if (flowNodes.length === 0) {
        message.warning(t('orchestrator.messages.planEmpty'));
        return;
      }
      setNodes(flowNodes);
      setEdges(flowEdges);
      useWorkflowStore.setState({ nodes: flowNodes, edges: flowEdges });
      setTimeout(() => useWorkflowStore.getState().saveToIndexedDB(), 0);
      message.success(t('orchestrator.messages.planImported', { count: flowNodes.length }));
      setAgentDrawerOpen(false);
    };

    if (nodes.length > 0) {
      Modal.confirm({
        title: t('orchestrator.confirm.overwriteTitle'),
        content: t('orchestrator.confirm.overwriteContent', { count: nodes.length }),
        okText: t('orchestrator.confirm.overwriteOk'),
        cancelText: t('common.cancel'),
        onOk: doImport,
      });
      return;
    }
    doImport();
  }, [nodes.length, setNodes, setEdges, message, t]);

  const exportAgentPlanAsLangGraph = useCallback(async (includePython = false) => {
    if (agentResult?.plan == null || typeof agentResult.plan !== 'object') {
      message.warning(t('orchestrator.messages.noPlanExport'));
      return;
    }
    await exportPlanAsLangGraph(
      agentResult.plan as Record<string, unknown>,
      'plan',
      includePython,
      String(agentResult.intent_id ?? ''),
    );
  }, [agentResult, exportPlanAsLangGraph, message, t]);

  const exportCanvasAsLangGraph = useCallback(async (pushToStore: () => void) => {
    pushToStore();
    const { graph } = useWorkflowStore.getState().exportWorkflow();
    if (Object.keys(graph).length === 0) {
      message.warning(t('orchestrator.messages.canvasEmptyExport'));
      return;
    }
    await exportPlanAsLangGraph(graph as Record<string, unknown>, 'canvas', false);
  }, [exportPlanAsLangGraph, message, t]);

  return {
    agentDrawerOpen,
    setAgentDrawerOpen,
    agentQuery,
    setAgentQuery,
    agentLoading,
    agentResult,
    handleAgentQuery,
    handlePlanOnly,
    importPlanToCanvas,
    exportAgentPlanAsLangGraph,
    exportCanvasAsLangGraph,
  };
}
