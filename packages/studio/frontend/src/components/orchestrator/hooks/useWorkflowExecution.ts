import { useCallback, useEffect, useRef, useState } from 'react';
import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import type { Edge, Node } from 'reactflow';
import { App } from 'antd';
import { useI18n } from '@/i18n';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { useEngineStore } from '@/store/useEngineStore';
import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';
import { useEventStore } from '@/store/useEventStore';
import type { ExecutionLog, WorkflowNodeData, ECM } from '@/types';
import { getWsManager } from '@/engine/ws/WsConnectionManager';
import { getErrorMessage } from '@/api/client';
import {
  executeWorkflow as executeWorkflowApi,
  stopWorkflow as stopWorkflowApi,
} from '@/api/workflows';

interface UseWorkflowExecutionParams {
  nodes: Node<WorkflowNodeData>[];
  nodesRef: MutableRefObject<Node<WorkflowNodeData>[]>;
  setNodes: Dispatch<SetStateAction<Node<WorkflowNodeData>[]>>;
  setEdges: Dispatch<SetStateAction<Edge[]>>;
  pushToStore: () => void;
  engineMode: 'mock' | 'real';
}

function setEdgeFlowState(
  setEdges: Dispatch<SetStateAction<Edge[]>>,
  activeNodeId: string | null,
) {
  setEdges((eds) =>
    eds.map((e) => ({
      ...e,
      data: {
        ...e.data,
        status: activeNodeId && (e.source === activeNodeId || e.target === activeNodeId)
          ? 'flowing'
          : undefined,
      },
    })),
  );
}

function clearEdgeFlowState(setEdges: Dispatch<SetStateAction<Edge[]>>) {
  setEdges((eds) =>
    eds.map((e) => ({
      ...e,
      data: { ...e.data, status: undefined },
    })),
  );
}

export function useWorkflowExecution({
  nodes,
  nodesRef,
  setNodes,
  setEdges,
  pushToStore,
  engineMode,
}: UseWorkflowExecutionParams) {
  const { t } = useI18n();
  const { message } = App.useApp();
  const engine = useEngineStore((s) => s.getEngine());
  const addEvent = useEventStore((s) => s.addEvent);
  const executePlan = useAgentRuntimeStore((s) => s.executePlan);
  const executionStatus = useWorkflowStore((s) => s.executionStatus);

  const [executionProgress, setExecutionProgress] = useState<{ completed: number; total: number } | null>(null);
  const [, setLogs] = useState<ExecutionLog[]>([]);
  const logPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastWfIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (executionStatus === 'running' && engineMode === 'mock') {
      logPollRef.current = setInterval(() => {
        const engineLogs = useEngineStore.getState().getEngine().getLogs?.() || [];
        setLogs(engineLogs);
      }, 200);
    } else if (logPollRef.current) {
      clearInterval(logPollRef.current);
      logPollRef.current = null;
    }
    return () => {
      if (logPollRef.current) clearInterval(logPollRef.current);
    };
  }, [executionStatus, engineMode]);

  const runWorkflowExecution = useCallback(async () => {
    pushToStore();
    const { graph } = useWorkflowStore.getState().exportWorkflow();

    if (Object.keys(graph).length === 0) {
      message.warning(t('orchestrator.messages.addNodesFirst'));
      return;
    }

    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, status: 'idle', result: undefined, error: undefined },
      })),
    );

    setLogs([]);
    useWorkflowStore.setState({ executionStatus: 'running' });
    setExecutionProgress({ completed: 0, total: nodes.length });
    message.info(t('orchestrator.messages.executing'));

    const mode = useEngineStore.getState().mode;
    const agentRuntime = useAgentRuntimeStore.getState();

    const bumpProgress = () => {
      setExecutionProgress((prev) =>
        prev ? { ...prev, completed: Math.min(prev.completed + 1, prev.total) } : null,
      );
    };

    try {
      if (mode === 'mock') {
        const handler = (ecm: ECM) => {
          addEvent('node.event', ecm);
        };
        engine.onEvent(handler);

        const graphResults = await engine.executeWorkflow(graph, (nodeName, status, result) => {
          if (status === 'completed' || status === 'failed') bumpProgress();
          const currentNodes = nodesRef.current;
          const n = currentNodes.find((x) => x.id === nodeName || x.data.task === nodeName);
          if (n) {
            if (status === 'running') {
              setEdgeFlowState(setEdges, n.id);
            }
            setNodes((nds) =>
              nds.map((nd) =>
                nd.id === n.id
                  ? {
                      ...nd,
                      data: {
                        ...nd.data,
                        status: status as WorkflowNodeData['status'],
                        result,
                        error: status === 'failed' ? String(result) : undefined,
                      },
                    }
                  : nd,
              ),
            );
          }
        });

        // Fallback: ensure final state if bus callbacks were missed
        if (graphResults && typeof graphResults === 'object') {
          setNodes((nds) =>
            nds.map((nd) => {
              if (!(nd.id in graph)) return nd;
              const nodeResult = (graphResults as Record<string, unknown>)[nd.id];
              if (nodeResult === undefined && nd.data.status !== 'failed') return nd;
              return {
                ...nd,
                data: {
                  ...nd.data,
                  status: nd.data.status === 'failed' ? 'failed' : 'completed',
                  result: nodeResult,
                },
              };
            }),
          );
        }

        engine.offEvent(handler);
        setLogs(engine.getLogs?.() || []);
      } else if (agentRuntime.runtimeMode === 'agent' && agentRuntime.agentActive) {
        const result = await executePlan(graph as Record<string, unknown>);
        const rawResults = (result.raw_results ?? {}) as Record<string, unknown>;
        setNodes((nds) =>
          nds.map((nd) => {
            const nodeResult = rawResults[nd.id];
            if (nodeResult !== undefined) {
              return {
                ...nd,
                data: { ...nd.data, status: 'completed' as const, result: nodeResult },
              };
            }
            return nd;
          }),
        );
        message.success(t('orchestrator.messages.agentExecuted', { intentId: String(result.intent_id ?? '') }));
        useWorkflowStore.setState({ executionStatus: 'completed' });
        await useWorkflowStore.getState().saveToIndexedDB();
        setExecutionProgress(null);
        return;
      } else {
        const wsManager = getWsManager();
        const updateNodeStatus = (nodeName: string, status: string, result?: unknown) => {
          if (status === 'completed' || status === 'failed') bumpProgress();
          const currentNodes = nodesRef.current;
          const n = currentNodes.find((x) => x.id === nodeName || x.data.task === nodeName);
          if (!n) return;
          if (status === 'running') {
            setEdgeFlowState(setEdges, n.id);
          }
          setNodes((nds) =>
            nds.map((nd) =>
              nd.id === n.id
                ? {
                    ...nd,
                    data: {
                      ...nd.data,
                      status: status as WorkflowNodeData['status'],
                      result,
                      error: status === 'failed' ? String(result) : undefined,
                    },
                  }
                : nd,
            ),
          );
        };

        const cleanup = wsManager.onWorkflowStatus((nodeName, status, result) => {
          updateNodeStatus(nodeName, status, result);
        });

        const execResp = await executeWorkflowApi(graph as Record<string, unknown>);
        lastWfIdRef.current = execResp.wf_id;

        const nodeResults =
          execResp.results
          ?? execResp.result?.results
          ?? (typeof execResp.result === 'object' && execResp.result && 'results' in execResp.result
            ? (execResp.result as { results?: Record<string, unknown> }).results
            : undefined);

        if (nodeResults && typeof nodeResults === 'object') {
          for (const [nodeId, nodeResult] of Object.entries(nodeResults)) {
            updateNodeStatus(nodeId, 'completed', nodeResult);
          }
        }

        cleanup();

        const finalStatus = execResp.status ?? execResp.result?.status ?? 'completed';
        if (finalStatus === 'failed' || finalStatus === 'aborted') {
          throw new Error(
            execResp.result?.error
            || (finalStatus === 'aborted'
              ? t('orchestrator.messages.workflowAborted')
              : t('orchestrator.messages.workflowFailed')),
          );
        }
      }

      useWorkflowStore.setState({ executionStatus: 'completed' });
      await useWorkflowStore.getState().saveToIndexedDB();
      message.success(t('orchestrator.messages.workflowCompleted'));
    } catch (err: unknown) {
      useWorkflowStore.setState({ executionStatus: 'failed' });
      await useWorkflowStore.getState().saveToIndexedDB();
      const error = err instanceof Error ? err.message : String(err);
      message.error(t('orchestrator.messages.executeFailed', { error }));
    } finally {
      clearEdgeFlowState(setEdges);
      setExecutionProgress(null);
    }
  }, [pushToStore, setNodes, setEdges, engine, addEvent, nodes, nodesRef, message, executePlan, t]);

  const stopExecution = useCallback(async () => {
    const wfId = lastWfIdRef.current;
    if (engineMode === 'real' && wfId) {
      try {
        await stopWorkflowApi(wfId);
      } catch (err) {
        message.warning(getErrorMessage(err));
      }
    }
    lastWfIdRef.current = null;
    useWorkflowStore.setState({ executionStatus: 'idle' });
    if (logPollRef.current) clearInterval(logPollRef.current);
    message.info(t('orchestrator.messages.stopped'));
  }, [engineMode, message, t]);

  return {
    runWorkflowExecution,
    stopExecution,
    executionProgress,
  };
}
