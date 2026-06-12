import { useState, useCallback, useEffect } from 'react';
import {
  useNodesState, useEdgesState, addEdge, type Node, type Connection,
} from 'reactflow';
import { Form, App } from 'antd';
import type { ChatflowNodeData } from '@/types';
import dbManager from '@/persistence/IndexedDBManager';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { useEngineStore } from '@/store/useEngineStore';
import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';
import { getErrorMessage } from '@/api';
import { executeChatflowWithAgent } from '@/utils/chatflowTopology';
import { useI18n } from '@/i18n';
import type { ChatMessage } from '@/components/chatflow/ChatflowPreviewPanel';

export function useChatflowPage() {
  const { message } = App.useApp();
  const { t } = useI18n();
  const engineMode = useEngineStore((s) => s.mode);
  const runtimeMode = useAgentRuntimeStore((s) => s.runtimeMode);
  const agentActive = useAgentRuntimeStore((s) => s.agentActive);
  const fetchRuntime = useAgentRuntimeStore((s) => s.fetchRuntime);
  const runAgentQuery = useAgentRuntimeStore((s) => s.runQuery);
  const planOnly = useAgentRuntimeStore((s) => s.planOnly);

  const [nodes, setNodes, onNodesChange] = useNodesState<ChatflowNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node<ChatflowNodeData> | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [agentLoading, setAgentLoading] = useState(false);
  const [useAgentMode, setUseAgentMode] = useState(true);
  const [lastIntentId, setLastIntentId] = useState('');
  const [form] = Form.useForm();

  useEffect(() => {
    if (engineMode === 'real') {
      fetchRuntime();
    }
  }, [engineMode, fetchRuntime]);

  const agentAvailable = engineMode === 'real' && runtimeMode === 'agent' && agentActive;

  const labelForType = useCallback(
    (nodeType: ChatflowNodeData['nodeType']) => {
      const map: Record<ChatflowNodeData['nodeType'], string> = {
        user_input: t('chatflow.userInput'),
        ai_reply: t('chatflow.aiReply'),
        condition: t('chatflow.condition'),
        variable: t('chatflow.variable'),
      };
      return map[nodeType];
    },
    [t],
  );

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node<ChatflowNodeData>) => {
      setSelectedNode(node);
      form.setFieldsValue(node.data);
      setDrawerOpen(true);
    },
    [form],
  );

  const addNode = useCallback(
    (nodeType: ChatflowNodeData['nodeType']) => {
      const id = `chat_${Date.now()}`;
      const newNode: Node<ChatflowNodeData> = {
        id,
        type: 'chatflowNode',
        position: { x: 100 + Math.random() * 300, y: 100 + Math.random() * 200 },
        data: {
          label: `${labelForType(nodeType)} ${nodes.filter((n) => n.type === 'chatflowNode').length + 1}`,
          nodeType,
          prompt: '',
          variable_mapping: {},
          condition: '',
        },
      };
      setNodes((nds) => [...nds, newNode]);
      message.success(`${labelForType(nodeType)} added`);
    },
    [labelForType, nodes, setNodes, message],
  );

  const deleteNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
      if (selectedNode?.id === nodeId) {
        setDrawerOpen(false);
        setSelectedNode(null);
      }
    },
    [selectedNode, setNodes, setEdges],
  );

  const saveNodeChanges = useCallback(async () => {
    const values = await form.validateFields();
    if (!selectedNode) return;
    setNodes((nds) =>
      nds.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, ...values } } : n)),
    );
    message.success('Node updated');
    setDrawerOpen(false);
  }, [form, selectedNode, setNodes, message]);

  const handleSendMessage = useCallback(async () => {
    if (!chatInput.trim()) return;
    const text = chatInput.trim();
    setChatMessages((prev) => [...prev, { role: 'user', content: text }]);
    setChatInput('');

    if (agentAvailable && useAgentMode) {
      setAgentLoading(true);
      try {
        const result = await runAgentQuery(text);
        const answer = String(result.answer ?? JSON.stringify(result, null, 2));
        const intentId = String(result.intent_id ?? '');
        setLastIntentId(intentId);
        setChatMessages((prev) => [
          ...prev,
          {
            role: 'ai',
            content: answer,
            meta: intentId ? `intent_id: ${intentId} · status: ${String(result.status ?? '')}` : undefined,
          },
        ]);
        if (result.status === 'plan_rejected') {
          message.warning('Plan rejected');
        }
      } catch (e) {
        message.error(getErrorMessage(e));
        setChatMessages((prev) => [...prev, { role: 'ai', content: getErrorMessage(e) }]);
      } finally {
        setAgentLoading(false);
      }
      return;
    }

    setTimeout(() => {
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'ai',
          content: `Echo: "${text}"\n\n(Mock) Enable live mode + Agent runtime for run_query.`,
        },
      ]);
    }, 300);
  }, [chatInput, agentAvailable, useAgentMode, runAgentQuery, message]);

  const handlePlanOnlyFromChat = useCallback(async () => {
    if (!chatInput.trim()) {
      message.warning('Enter a message first');
      return;
    }
    if (!agentAvailable) {
      message.warning('Requires live mode + Agent runtime');
      return;
    }
    setAgentLoading(true);
    try {
      const result = await planOnly(chatInput.trim());
      setLastIntentId(String(result.intent_id ?? ''));
      setChatMessages((prev) => [
        ...prev,
        { role: 'user', content: chatInput.trim() },
        {
          role: 'ai',
          content: JSON.stringify(result.plan, null, 2),
          meta: `plan-only · intent_id: ${String(result.intent_id ?? '')}`,
        },
      ]);
      setChatInput('');
      message.success('Plan generated (not executed)');
    } catch (e) {
      message.error(getErrorMessage(e));
    } finally {
      setAgentLoading(false);
    }
  }, [chatInput, agentAvailable, planOnly, message]);

  const clearCanvas = useCallback(() => {
    setNodes([]);
    setEdges([]);
    setChatMessages([]);
    message.info('Canvas cleared');
  }, [setNodes, setEdges, message]);

  const saveChatflow = useCallback(async () => {
    try {
      const chatflowId = useWorkflowStore.getState().currentWorkflowId || 'chatflow_default';
      await dbManager.saveWorkflow({
        id: chatflowId,
        name: `Chatflow ${chatflowId.slice(-6)}`,
        nodes: nodes as unknown as Parameters<typeof dbManager.saveWorkflow>[0]['nodes'],
        edges,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      });
      message.success('Chatflow saved');
    } catch {
      message.error('Save failed');
    }
  }, [nodes, edges, message]);

  const loadChatflow = useCallback(async () => {
    try {
      const workflows = await dbManager.getAllWorkflows();
      if (workflows.length > 0) {
        const latest = workflows.sort((a, b) => b.updatedAt - a.updatedAt)[0];
        setNodes(latest.nodes as unknown as import('reactflow').Node<ChatflowNodeData>[]);
        setEdges(latest.edges);
        message.success('Chatflow loaded');
      } else {
        message.info('No saved chatflow');
      }
    } catch {
      message.error('Load failed');
    }
  }, [setNodes, setEdges, message]);

  const executeChatflow = useCallback(async () => {
    if (nodes.length === 0) {
      message.warning('Add nodes first');
      return;
    }
    if (agentAvailable && useAgentMode) {
      setAgentLoading(true);
      try {
        const { steps, finalAnswer, intentId } = await executeChatflowWithAgent(
          nodes,
          edges,
          (q) => runAgentQuery(q),
          chatInput.trim(),
        );
        setLastIntentId(intentId);
        setChatMessages((prev) => [
          ...prev,
          ...steps.map((s) => ({
            role: s.nodeType === 'user_input' ? 'user' : 'ai',
            content: `[${s.label}] ${s.output}${s.skipped ? ' (skipped)' : ''}`,
            meta: s.nodeType === 'ai_reply' ? `step · ${s.nodeId}` : undefined,
          })),
          { role: 'ai', content: finalAnswer || 'Done', meta: intentId ? `intent_id: ${intentId}` : undefined },
        ]);
        message.success(`Chatflow executed (${steps.length} steps)`);
      } catch (e) {
        message.error(getErrorMessage(e));
      } finally {
        setAgentLoading(false);
      }
      return;
    }
    message.info('Running chatflow (mock)…');
    setTimeout(() => message.success('Chatflow done (mock)'), 1500);
  }, [nodes, edges, agentAvailable, useAgentMode, runAgentQuery, chatInput, message]);

  const nodeCount = nodes.filter((n) => n.type === 'chatflowNode').length;

  return {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onNodeClick,
    selectedNode,
    drawerOpen,
    setDrawerOpen,
    form,
    chatMessages,
    chatInput,
    setChatInput,
    agentLoading,
    useAgentMode,
    setUseAgentMode,
    lastIntentId,
    engineMode,
    agentAvailable,
    nodeCount,
    addNode,
    deleteNode,
    saveNodeChanges,
    handleSendMessage,
    handlePlanOnlyFromChat,
    clearCanvas,
    saveChatflow,
    loadChatflow,
    executeChatflow,
    setChatMessages,
  };
}
