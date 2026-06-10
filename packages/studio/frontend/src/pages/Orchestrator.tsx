import { useCallback, useRef, useState, useMemo, useEffect } from 'react';
import ReactFlow, {
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  useReactFlow,
  Connection,
  Node,
  Edge,
  Panel,
  type NodeProps,
  Handle,
  Position,
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Button, Space, Tooltip, Drawer, Form, Input, InputNumber,
  Select, Tag, App, Dropdown, Divider, Spin, message, Tabs,
  Table, Badge, Popconfirm, List, Typography, Alert, Collapse,
} from 'antd';
const { TextArea } = Input;
import type { MenuProps } from 'antd';
import { API_BASE_URL } from '@/utils/api';
import {
  PlayCircleOutlined, StopOutlined, SaveOutlined,
  FolderOpenOutlined, ExportOutlined, UndoOutlined,
  RedoOutlined, PartitionOutlined, PlusOutlined,
  DeleteOutlined, CopyOutlined, AppstoreAddOutlined,
  CloseOutlined, BranchesOutlined, SyncOutlined, CodeOutlined,
  ApiOutlined, ThunderboltOutlined, FileTextOutlined,
} from '@ant-design/icons';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { useEngineStore } from '@/store/useEngineStore';
import { useEventStore } from '@/store/useEventStore';
import { useVariableStore } from '@/store/useVariableStore';
import type { WorkflowNodeData, ExecutionLog, VariableDef, ConditionNodeData, CodeNodeData } from '@/types';
import { getWsManager } from '@/engine/ws/WsConnectionManager';

const { Text } = Typography;

// ========== 自定义任务节点 ==========
function TaskNode({ data, selected }: NodeProps<WorkflowNodeData>) {
  const statusColors: Record<string, string> = {
    idle: '#d9d9d9',
    running: '#1890ff',
    completed: '#52c41a',
    failed: '#ff4d4f',
  };

  const variantColors: Record<string, string> = {
    task: '#6366f1',
    dynamic: '#ff7a45',
    subgraph: '#52c41a',
    condition: '#722ed1',
    loop: '#fa8c16',
    code: '#f5222d',
    http: '#1890ff',
    trigger: '#13c2c2',
  };

  const variant = data.variant || 'task';
  const variantColor = variantColors[variant] || variantColors.task;

  const inputColor = '#52c41a';
  const outputColor = '#ff7a45';

  // 条件节点 - 多个输出端口
  const isCondition = variant === 'condition';
  const conditionData = (data as unknown as { condition_data?: ConditionNodeData }).condition_data;
  const branches = conditionData?.branches || [{ id: 'true', label: '是', condition: '' }, { id: 'false', label: '否', condition: '' }];

  return (
    <div
      className={`task-node status-${data.status} variant-${variant}`}
      style={{ borderColor: selected ? variantColor : statusColors[data.status] }}
    >
      {/* 输入端 */}
      <Handle
        type="target"
        position={Position.Left}
        isConnectable
        style={{
          width: 16, height: 16,
          background: '#fff',
          border: `3px solid ${inputColor}`,
          borderRadius: 4,
        }}
      />
      <div className="node-label" style={{ color: variantColor }}>{data.label}</div>
      {data.skills.length > 0 && (
        <div className="node-skills">
          {data.skills.map(s => <span key={s} className="node-skill-tag" style={{ background: variantColor + '18', color: variantColor }}>{s}</span>)}
        </div>
      )}
      {isCondition && (
        <div style={{ fontSize: 10, color: '#888', marginTop: 4 }}>
          {branches.length} 个分支
        </div>
      )}
      <div className="node-status-badge">
        {data.status === 'running' && <Tag color="processing">运行中</Tag>}
        {data.status === 'completed' && <Tag color="success">完成</Tag>}
        {data.status === 'failed' && <Tag color="error">失败</Tag>}
        {data.status === 'idle' && <Tag>等待</Tag>}
        {data.error && <span style={{ color: '#ff4d4f', fontSize: 10 }}> {data.error}</span>}
      </div>
      {/* 条件节点 - 多个输出端 */}
      {isCondition ? (
        branches.map((branch, idx) => (
          <Handle
            key={branch.id}
            type="source"
            position={Position.Right}
            id={`branch-${branch.id}`}
            isConnectable
            style={{
              width: 14, height: 14,
              background: '#722ed1',
              border: '2px solid #fff',
              right: -8,
              top: `${30 + idx * 25}%`,
            }}
          >
            <span style={{ fontSize: 9, marginLeft: 18, color: '#722ed1' }}>{branch.label}</span>
          </Handle>
        ))
      ) : (
        /* 普通输出端 */
        <Handle
          type="source"
          position={Position.Right}
          isConnectable
          style={{
            width: 14, height: 14,
            background: outputColor,
            border: '2px solid #fff',
          }}
        />
      )}
    </div>
  );
}

const nodeTypes = { taskNode: TaskNode };

// ========== 可删除连线组件 ==========
function DeletableEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const { deleteElements } = useReactFlow();
  const { message } = App.useApp();

  const handleDelete = () => {
    deleteElements({ edges: [{ id }] });
    message.info('连线已删除');
  };

  return (
    <>
      <BaseEdge id={id} path={edgePath} style={style} markerEnd={markerEnd} />
      <EdgeLabelRenderer>
        <div
          className="edge-delete-btn"
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            pointerEvents: 'all',
          }}
          onClick={handleDelete}
        >
          <CloseOutlined style={{ fontSize: 11 }} />
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

const edgeTypes = { deletable: DeletableEdge };

// ========== 内置模板 ==========
const builtinTemplates: { key: string; label: string; description: string }[] = [
  {
    key: 'rag_pipeline',
    label: 'RAG 流水线',
    description: '检索增强生成：检索 → 重排 → 生成回答',
  },
  {
    key: 'debate_decision',
    label: '辩论式决策',
    description: '多 Agent 并行发表观点 → 汇总 Agent 总结结论',
  },
  {
    key: 'hierarchical_planning',
    label: '分层规划执行',
    description: '规划 → 各 Agent 并行执行 → 验证检查',
  },
];

const templateData: Record<string, { nodes: Node<WorkflowNodeData>[]; edges: Edge[] }> = {
  rag_pipeline: {
    nodes: [
      { id: 'retrieve', type: 'taskNode', position: { x: 50, y: 100 }, data: { label: '文档检索', task: 'document_retrieval', skills: ['search', 'embedding'], variant: 'task', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'abort', expectation: { state_key: 'retrieved_docs', expected_schema: {}, validation: '', deadline: 30, use_json_schema: false } } },
      { id: 'rerank', type: 'taskNode', position: { x: 270, y: 100 }, data: { label: '结果重排', task: 'result_reranking', skills: ['nlp', 'ranking'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'abort', expectation: { state_key: 'ranked_docs', expected_schema: {}, validation: '', deadline: 20, use_json_schema: false } } },
      { id: 'generate', type: 'taskNode', position: { x: 490, y: 100 }, data: { label: '生成回答', task: 'answer_generation', skills: ['llm', 'summarization'], variant: 'subgraph', status: 'idle', retry_policy: { max_attempts: 3, backoff_type: 'exponential', backoff_base: 1, max_backoff: 30 }, on_failure: 'abort', expectation: { state_key: 'final_answer', expected_schema: {}, validation: '', deadline: 60, use_json_schema: false } } },
    ],
    edges: [
      { id: 'e-retrieve-rerank', source: 'retrieve', target: 'rerank', type: 'deletable' },
      { id: 'e-rerank-generate', source: 'rerank', target: 'generate', type: 'deletable' },
    ],
  },
  debate_decision: {
    nodes: [
      { id: 'issue', type: 'taskNode', position: { x: 250, y: 20 }, data: { label: '问题拆解', task: 'issue_decomposition', skills: ['planning', 'analysis'], variant: 'task', status: 'idle', on_failure: 'abort', expectation: { state_key: 'decomposed_issue', expected_schema: {}, validation: '', deadline: 15, use_json_schema: false } } },
      { id: 'analyst_a', type: 'taskNode', position: { x: 50, y: 140 }, data: { label: '分析师 A (乐观)', task: 'optimistic_analysis', skills: ['analysis', 'reasoning'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'skip', expectation: { state_key: 'opinion_a', expected_schema: {}, validation: '', deadline: 30, use_json_schema: false } } },
      { id: 'analyst_b', type: 'taskNode', position: { x: 250, y: 140 }, data: { label: '分析师 B (悲观)', task: 'pessimistic_analysis', skills: ['analysis', 'reasoning'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'skip', expectation: { state_key: 'opinion_b', expected_schema: {}, validation: '', deadline: 30, use_json_schema: false } } },
      { id: 'analyst_c', type: 'taskNode', position: { x: 450, y: 140 }, data: { label: '分析师 C (中立)', task: 'neutral_analysis', skills: ['analysis', 'reasoning'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'skip', expectation: { state_key: 'opinion_c', expected_schema: {}, validation: '', deadline: 30, use_json_schema: false } } },
      { id: 'summary', type: 'taskNode', position: { x: 250, y: 270 }, data: { label: '汇总结论', task: 'conclusion_synthesis', skills: ['summarization', 'decision'], variant: 'subgraph', status: 'idle', retry_policy: { max_attempts: 3, backoff_type: 'exponential', backoff_base: 1, max_backoff: 30 }, on_failure: 'abort', expectation: { state_key: 'final_decision', expected_schema: {}, validation: '', deadline: 45, use_json_schema: false } } },
    ],
    edges: [
      { id: 'e-issue-a', source: 'issue', target: 'analyst_a', type: 'deletable' },
      { id: 'e-issue-b', source: 'issue', target: 'analyst_b', type: 'deletable' },
      { id: 'e-issue-c', source: 'issue', target: 'analyst_c', type: 'deletable' },
      { id: 'e-a-summary', source: 'analyst_a', target: 'summary', type: 'deletable' },
      { id: 'e-b-summary', source: 'analyst_b', target: 'summary', type: 'deletable' },
      { id: 'e-c-summary', source: 'analyst_c', target: 'summary', type: 'deletable' },
    ],
  },
  hierarchical_planning: {
    nodes: [
      { id: 'planner', type: 'taskNode', position: { x: 250, y: 20 }, data: { label: '任务规划', task: 'task_planning', skills: ['planning', 'decomposition'], variant: 'task', status: 'idle', on_failure: 'abort', expectation: { state_key: 'task_plan', expected_schema: {}, validation: '', deadline: 20, use_json_schema: false } } },
      { id: 'exec_1', type: 'taskNode', position: { x: 50, y: 150 }, data: { label: '执行 Agent 1 (数据采集)', task: 'data_collection', skills: ['crawling', 'data_processing'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 3, backoff_type: 'exponential', backoff_base: 1, max_backoff: 30 }, on_failure: 'skip', expectation: { state_key: 'collected_data', expected_schema: {}, validation: '', deadline: 60, use_json_schema: false } } },
      { id: 'exec_2', type: 'taskNode', position: { x: 250, y: 150 }, data: { label: '执行 Agent 2 (模型训练)', task: 'model_training', skills: ['ml', 'training'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'exponential', backoff_base: 2, max_backoff: 60 }, on_failure: 'abort', expectation: { state_key: 'trained_model', expected_schema: {}, validation: '', deadline: 300, use_json_schema: false } } },
      { id: 'exec_3', type: 'taskNode', position: { x: 450, y: 150 }, data: { label: '执行 Agent 3 (特征工程)', task: 'feature_engineering', skills: ['data_analysis', 'preprocessing'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 15 }, on_failure: 'skip', expectation: { state_key: 'features', expected_schema: {}, validation: '', deadline: 45, use_json_schema: false } } },
      { id: 'validator', type: 'taskNode', position: { x: 250, y: 280 }, data: { label: '结果验证', task: 'result_validation', skills: ['testing', 'evaluation'], variant: 'subgraph', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'abort', expectation: { state_key: 'validation_report', expected_schema: {}, validation: '', deadline: 30, use_json_schema: false } } },
    ],
    edges: [
      { id: 'e-planner-exec1', source: 'planner', target: 'exec_1', type: 'deletable' },
      { id: 'e-planner-exec2', source: 'planner', target: 'exec_2', type: 'deletable' },
      { id: 'e-planner-exec3', source: 'planner', target: 'exec_3', type: 'deletable' },
      { id: 'e-exec1-validator', source: 'exec_1', target: 'validator', type: 'deletable' },
      { id: 'e-exec2-validator', source: 'exec_2', target: 'validator', type: 'deletable' },
      { id: 'e-exec3-validator', source: 'exec_3', target: 'validator', type: 'deletable' },
    ],
  },
};

// ========== 节点类型配置 ==========
interface NodeTypeConfig {
  type: string;
  label: string;
  variant: WorkflowNodeData['variant'];
  color: string;
  icon: JSX.Element;
}

const nodeTypeConfigs: NodeTypeConfig[] = [
  { type: 'taskNode', label: '任务节点', variant: 'task', color: '#6366f1', icon: <span style={{ color: '#6366f1' }}>⬡</span> },
  { type: 'taskNode', label: '动态节点', variant: 'dynamic', color: '#ff7a45', icon: <span style={{ color: '#ff7a45' }}>⬡</span> },
  { type: 'taskNode', label: '子图容器', variant: 'subgraph', color: '#52c41a', icon: <span style={{ color: '#52c41a' }}>⬡</span> },
  { type: 'taskNode', label: '条件分支', variant: 'condition', color: '#722ed1', icon: <BranchesOutlined style={{ color: '#722ed1' }} /> },
  { type: 'taskNode', label: '循环', variant: 'loop', color: '#fa8c16', icon: <SyncOutlined style={{ color: '#fa8c16' }} /> },
  { type: 'taskNode', label: '代码执行', variant: 'code', color: '#f5222d', icon: <CodeOutlined style={{ color: '#f5222d' }} /> },
  { type: 'taskNode', label: 'HTTP请求', variant: 'http', color: '#1890ff', icon: <ApiOutlined style={{ color: '#1890ff' }} /> },
  { type: 'taskNode', label: '触发器', variant: 'trigger', color: '#13c2c2', icon: <ThunderboltOutlined style={{ color: '#13c2c2' }} /> },
];

// 日志级别颜色
const logLevelColors: Record<string, string> = {
  info: '#1890ff',
  warn: '#faad14',
  error: '#ff4d4f',
  debug: '#8c8c8c',
};

// ========== 编排画布页面 ==========
export default function OrchestratorPage() {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node<WorkflowNodeData> | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('config');

  // 日志状态
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [logFilter, setLogFilter] = useState<string>('all');
  const logPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { message } = App.useApp();
  const store = useWorkflowStore();
  const engine = useEngineStore().getEngine();
  const addEvent = useEventStore(s => s.addEvent);
  const variables = useVariableStore(s => s.variables);
  const addVariable = useVariableStore(s => s.addVariable);
  const updateVariable = useVariableStore(s => s.updateVariable);
  const deleteVariable = useVariableStore(s => s.deleteVariable);

  // 日志轮询
  useEffect(() => {
    if (useWorkflowStore.getState().executionStatus === 'running') {
      logPollRef.current = setInterval(() => {
        const engineLogs = useEngineStore.getState().getEngine().getLogs?.() || [];
        setLogs(engineLogs);
      }, 200);
    }
    return () => {
      if (logPollRef.current) clearInterval(logPollRef.current);
    };
  }, [useWorkflowStore.getState().executionStatus]);

  // 组件挂载时从 IndexedDB 加载持久化的工作流
  useEffect(() => {
    const loadPersistedWorkflow = async () => {
      try {
        const workflows = await useWorkflowStore.getState().listWorkflows();
        if (workflows.length > 0) {
          const latest = workflows.sort((a, b) => b.updatedAt - a.updatedAt)[0];
          await useWorkflowStore.getState().loadFromIndexedDB(latest.id);
          const state = useWorkflowStore.getState();
          setNodes(state.nodes);
          setEdges(state.edges);
        }
      } catch {
        // 首次访问或加载失败，使用空画布
      }
    };
    loadPersistedWorkflow();
  }, [setNodes, setEdges]);

  // 同步 store -> 本地状态
  const pushToStore = useCallback(() => {
    useWorkflowStore.setState({ nodes, edges });
    setTimeout(() => useWorkflowStore.getState().saveToIndexedDB(), 0);
  }, [nodes, edges]);

  // 连接节点
  const onConnect = useCallback((params: Connection) => {
    const edge = { ...params, id: `e-${params.source}-${params.target}`, type: 'deletable' };
    setEdges((eds) => addEdge(edge, eds));
  }, [setEdges]);

  // 拖拽添加节点
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  // 双击节点库项直接添加到画布中央
  const onNodePanelDoubleClick = useCallback(
    (cfg: NodeTypeConfig) => {
      if (!reactFlowInstance) {
        // Fallback: if instance not ready, add to default position
        setNodes((nds) => [
          ...nds,
          {
            id: `node_${Date.now()}`,
            type: cfg.type,
            position: { x: 250, y: 200 },
            data: {
              label: cfg.label,
              task: cfg.label,
              variant: cfg.variant,
              skills: [],
              status: 'idle',
            },
          },
        ]);
        return;
      }
      const center = reactFlowInstance.screenToFlowPosition({
        x: reactFlowInstance.getWidth() / 2,
        y: reactFlowInstance.getHeight() / 2,
      });
      const newNode: Node<WorkflowNodeData> = {
        id: `node_${Date.now()}`,
        type: cfg.type,
        position: { x: center.x - 75, y: center.y - 20 },
        data: {
          label: cfg.label,
          task: cfg.label,
          variant: cfg.variant,
          skills: [],
          status: 'idle',
          ...(cfg.variant === 'condition' ? {
            condition_data: {
              condition: '',
              branches: [
                { id: 'true', label: '是', condition: '' },
                { id: 'false', label: '否', condition: '' },
              ],
              default_branch: 'false',
            } as unknown as WorkflowNodeData,
          } : {}),
          ...(cfg.variant === 'code' ? {
            code_data: {
              language: 'javascript',
              code: '// 在此编写代码\nfunction main(input) {\n  return { output: input };\n}',
              input_mapping: {},
              output_mapping: {},
            } as unknown as WorkflowNodeData,
          } : {}),
        },
      };
      setNodes((nds) => [...nds, newNode]);
    },
    [reactFlowInstance, setNodes]
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData('application/reactflow-type');
      const label = event.dataTransfer.getData('application/reactflow-label');
      const variant = event.dataTransfer.getData('application/reactflow-variant') || 'task';
      if (!type || !reactFlowInstance) return;

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      }) as { x: number; y: number };

      const newNode: Node<WorkflowNodeData> = {
        id: `node_${Date.now()}`,
        type,
        position,
        data: {
          label: label || '新任务',
          task: label || '新任务',
          variant: variant as WorkflowNodeData['variant'],
          skills: [],
          status: 'idle',
          ...(variant === 'condition' ? {
            condition_data: {
              condition: '',
              branches: [
                { id: 'true', label: '是', condition: '' },
                { id: 'false', label: '否', condition: '' },
              ],
              default_branch: 'false',
            } as unknown as WorkflowNodeData,
          } : {}),
          ...(variant === 'code' ? {
            code_data: {
              language: 'javascript',
              code: '// 在此编写代码\nfunction main(input) {\n  return { output: input };\n}',
              input_mapping: {},
              output_mapping: {},
            } as unknown as WorkflowNodeData,
          } : {}),
        },
      };
      setNodes((nds) => [...nds, newNode]);
    },
    [reactFlowInstance, setNodes]
  );

  // 节点点击 → 配置面板
  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
    setDrawerOpen(true);
    setActiveTab('config');
  }, []);

  // 保存节点配置
  const saveNodeConfig = useCallback((values: Record<string, any>) => {
    if (!selectedNode) return;
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? {
              ...n,
              data: {
                ...n.data,
                label: values.label,
                task: values.task,
                skills: values.skills || [],
                retry_policy: values.max_attempts ? {
                  max_attempts: values.max_attempts,
                  backoff_type: values.backoff_type || 'constant',
                  backoff_base: values.backoff_base || 1,
                  max_backoff: values.max_backoff || 30,
                } : undefined,
                on_failure: values.on_failure,
                expectation: values.state_key ? {
                  state_key: values.state_key,
                  expected_schema: {},
                  validation: values.validation || '',
                  deadline: values.deadline || 30,
                  use_json_schema: false,
                } : undefined,
                ...(n.data.variant === 'condition' && values.branches ? {
                  condition_data: {
                    condition: values.condition || '',
                    branches: values.branches,
                    default_branch: values.default_branch,
                  },
                } : {}),
                ...(n.data.variant === 'code' ? {
                  code_data: {
                    language: values.language || 'javascript',
                    code: values.code || '',
                    input_mapping: values.input_mapping || {},
                    output_mapping: values.output_mapping || {},
                  },
                } : {}),
              },
            }
          : n
      )
    );
    setDrawerOpen(false);
    message.success('节点配置已保存');
  }, [selectedNode, setNodes]);

  // 删除选中节点
  const deleteSelectedNode = useCallback(() => {
    if (!selectedNode) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
    setDrawerOpen(false);
  }, [selectedNode, setNodes, setEdges]);

  // 执行工作流
  const executeWorkflow = useCallback(async () => {
    pushToStore();
    const { graph } = useWorkflowStore.getState().exportWorkflow();

    if (Object.keys(graph).length === 0) {
      message.warning('请先添加任务节点');
      return;
    }

    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, status: 'idle', result: undefined, error: undefined },
      }))
    );

    setLogs([]);
    useWorkflowStore.setState({ executionStatus: 'running' });
    message.info('工作流执行中...');

    const engineMode = useEngineStore.getState().mode;

    try {
      if (engineMode === 'mock') {
        const handler = (ecm: any) => {
          addEvent('node.event', ecm);
        };
        engine.onEvent(handler);

        await engine.executeWorkflow(graph, (nodeName, status, result) => {
          const n = nodes.find(x => x.id === nodeName || x.data.task === nodeName);
          if (n) {
            setNodes((nds) =>
              nds.map((nd) =>
                nd.id === n.id
                  ? { ...nd, data: { ...nd.data, status: status as any, result, error: status === 'failed' ? String(result) : undefined } }
                  : nd
              )
            );
          }
        });

        engine.offEvent(handler);
        // 获取日志
        const engineLogs = engine.getLogs?.() || [];
        setLogs(engineLogs);
      } else {
        const wsManager = getWsManager();
        const cleanup = wsManager.onWorkflowStatus((nodeName, status, result) => {
          const n = nodes.find(x => x.id === nodeName || x.data.task === nodeName);
          if (n) {
            setNodes((nds) =>
              nds.map((nd) =>
                nd.id === n.id
                  ? { ...nd, data: { ...nd.data, status: status as any, result, error: status === 'failed' ? String(result) : undefined } }
                  : nd
              )
            );
          }
        });

        await fetch(`${API_BASE_URL}/api/workflows/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ graph }),
        });

        cleanup();
      }

      useWorkflowStore.setState({ executionStatus: 'completed' });
      await useWorkflowStore.getState().saveToIndexedDB();
      message.success('工作流执行完成');
    } catch (err: any) {
      useWorkflowStore.setState({ executionStatus: 'failed' });
      await useWorkflowStore.getState().saveToIndexedDB();
      message.error(`执行失败: ${err.message}`);
    }
  }, [pushToStore, setNodes, engine, addEvent, nodes]);

  // 停止执行
  const stopExecution = useCallback(() => {
    useWorkflowStore.setState({ executionStatus: 'idle' });
    if (logPollRef.current) clearInterval(logPollRef.current);
    message.info('已停止');
  }, []);

  // 导出工作流为 .hflow 文件
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
    message.success('工作流已导出为 .hflow 文件');
  }, [pushToStore]);

  // 导入 .hflow 文件
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
            setNodes(data.nodes);
            setEdges(data.edges);
            useWorkflowStore.getState().loadWorkflow(data);
            message.success('工作流已导入');
          } else {
            message.error('无效的工作流文件');
          }
        } catch {
          message.error('无效的工作流文件');
        }
      };
      reader.readAsText(file);
    };
    input.click();
  }, [setNodes, setEdges]);

  // 批量导出
  const batchExportWorkflows = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/workflows/batch-export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!response.ok) throw new Error('批量导出失败');
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'workflows_batch.hflow';
      a.click();
      URL.revokeObjectURL(url);
      message.success(`已批量导出 ${data.count} 个工作流`);
    } catch {
      message.error('批量导出失败');
    }
  }, []);

  // 自动布局
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

  // 新建画布
  const newCanvas = useCallback(() => {
    setNodes([]);
    setEdges([]);
    useWorkflowStore.getState().reset();
  }, [setNodes, setEdges]);

  // 加载内置模板
  const loadTemplate = useCallback((key: string) => {
    const tmpl = templateData[key];
    if (!tmpl) return;
    setNodes(tmpl.nodes);
    setEdges(tmpl.edges);
    useWorkflowStore.getState().loadWorkflow(tmpl);
    message.success(`已加载"${builtinTemplates.find(t => t.key === key)?.label}"模板`);
  }, [setNodes, setEdges, message]);

  const executionStatus = useWorkflowStore(s => s.executionStatus);

  // 模板菜单项
  const templateMenuItems: MenuProps['items'] = builtinTemplates.map(t => ({
    key: t.key,
    label: (
      <div data-testid={`template-${t.key}`}>
        <div style={{ fontWeight: 600 }}>{t.label}</div>
        <div style={{ fontSize: 11, color: '#888' }}>{t.description}</div>
      </div>
    ),
  }));

  // 过滤后的日志
  const filteredLogs = useMemo(() => {
    if (logFilter === 'all') return logs;
    return logs.filter(log => log.level === logFilter);
  }, [logs, logFilter]);

  // 格式化时间
  const formatTime = (timestamp: number) => {
    const d = new Date(timestamp);
    return d.toLocaleTimeString('zh-CN', { hour12: false });
  };

  // 变量表单
  const [variableForm] = Form.useForm();
  const [varModalOpen, setVarModalOpen] = useState(false);
  const [editingVar, setEditingVar] = useState<VariableDef | null>(null);

  const handleSaveVariable = useCallback(async () => {
    try {
      const values = await variableForm.validateFields();
      let parsedValue = values.value;
      if (values.type === 'number') parsedValue = Number(values.value);
      else if (values.type === 'boolean') parsedValue = values.value === 'true' || values.value === true;
      else if (values.type === 'object' || values.type === 'array') {
        try { parsedValue = JSON.parse(values.value); } catch { message.error('无效的 JSON'); return; }
      }

      if (editingVar) {
        updateVariable(editingVar.id, { ...values, value: parsedValue });
        message.success('变量已更新');
      } else {
        addVariable({ ...values, value: parsedValue });
        message.success('变量已添加');
      }
      setVarModalOpen(false);
    } catch { /* ignore */ }
  }, [variableForm, editingVar, addVariable, updateVariable]);

  const varColumns = [
    { title: '名称', dataIndex: 'name', key: 'name', render: (t: string) => <Text code>{t}</Text> },
    { title: '类型', dataIndex: 'type', key: 'type', width: 80, render: (t: string) => <Tag>{t}</Tag> },
    { title: '值', dataIndex: 'value', key: 'value', ellipsis: true, render: (v: unknown) => String(v ?? '-') },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: unknown, record: VariableDef) => (
        <Space>
          <Button type="link" size="small" onClick={() => {
            setEditingVar(record);
            variableForm.setFieldsValue(record);
            setVarModalOpen(true);
          }}>编辑</Button>
          <Popconfirm title="确认删除" onConfirm={() => deleteVariable(record.id)}>
            <Button type="link" danger size="small">删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }} ref={reactFlowWrapper}>
      {/* 工具栏 */}
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Button icon={<PlusOutlined />} data-testid="btn-new" onClick={newCanvas}>新建</Button>
          <Dropdown menu={{ items: templateMenuItems, onClick: ({ key }) => loadTemplate(key) }}>
            <Button icon={<AppstoreAddOutlined />} data-testid="btn-template">模板</Button>
          </Dropdown>
          <Button icon={<FolderOpenOutlined />} data-testid="btn-import" onClick={importWorkflow}>导入</Button>
          <Button icon={<ExportOutlined />} data-testid="btn-export" onClick={exportWorkflow}>导出</Button>
          <Button icon={<ExportOutlined />} data-testid="btn-batch-export" onClick={batchExportWorkflows}>批量导出</Button>
          <Divider type="vertical" />
          <Button icon={<PartitionOutlined />} data-testid="btn-layout" onClick={autoLayout}>自动布局</Button>
          <Button icon={<UndoOutlined />} disabled data-testid="btn-undo">撤销</Button>
          <Button icon={<RedoOutlined />} disabled data-testid="btn-redo">重做</Button>
        </Space>
        <Space>
          {executionStatus === 'running' ? (
            <Button danger icon={<StopOutlined />} data-testid="btn-stop" onClick={stopExecution}>停止</Button>
          ) : (
            <Button type="primary" icon={<PlayCircleOutlined />} data-testid="btn-execute" onClick={executeWorkflow}>执行</Button>
          )}
        </Space>
      </div>

      {/* 面板：左侧节点库 + 中央画布 */}
      <div style={{ flex: 1, display: 'flex', gap: 0, border: '1px solid #f0f0f0', borderRadius: 8, overflow: 'hidden' }}>
        {/* 节点库 */}
        <div className="dnd-node-panel" style={{ width: 180, background: '#fafafa', borderRight: '1px solid #f0f0f0', padding: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 13 }}>节点库</div>
          {nodeTypeConfigs.map((cfg) => (
            <div
              key={cfg.label}
              className="dnd-node-item"
              data-testid={`node-${cfg.variant || 'task'}`}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('application/reactflow-type', cfg.type);
                e.dataTransfer.setData('application/reactflow-label', cfg.label);
                e.dataTransfer.setData('application/reactflow-variant', cfg.variant || 'task');
                e.dataTransfer.effectAllowed = 'move';
              }}
              onDoubleClick={() => onNodePanelDoubleClick(cfg)}
              title="双击添加到画布"
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
            >
              <span>{cfg.icon} {cfg.label}</span>
              <Button
                size="small"
                type="text"
                icon={<PlusOutlined />}
                data-testid={`btn-add-${cfg.variant || 'task'}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onNodePanelDoubleClick(cfg);
                }}
                style={{ padding: '0 4px', minWidth: 'auto', height: 'auto' }}
              />
            </div>
          ))}
        </div>

        {/* 画布 */}
        <div style={{ flex: 1 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={setReactFlowInstance}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            deleteKeyCode={['Backspace', 'Delete']}
            defaultEdgeOptions={{ type: 'deletable', style: { stroke: '#6366f1', strokeWidth: 2 }, deletable: true }}
            connectionLineStyle={{ stroke: '#6366f1', strokeWidth: 2, strokeDasharray: '5 5' }}
          >
            <Controls />
            <Background gap={16} color="#f0f0f0" />
            <MiniMap
              nodeColor={(n) => {
                const d = n.data as WorkflowNodeData;
                if (d.status === 'completed') return '#52c41a';
                if (d.status === 'running') return '#1890ff';
                if (d.status === 'failed') return '#ff4d4f';
                return '#d9d9d9';
              }}
            />
          </ReactFlow>
        </div>
      </div>

      {/* 节点配置抽屉 */}
      <Drawer
        title="节点配置"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={500}
        extra={
          <Button danger icon={<DeleteOutlined />} onClick={deleteSelectedNode}>删除节点</Button>
        }
      >
        {selectedNode && (
          <Form
            layout="vertical"
            initialValues={{
              label: selectedNode.data.label,
              task: selectedNode.data.task,
              skills: selectedNode.data.skills,
              max_attempts: selectedNode.data.retry_policy?.max_attempts,
              backoff_type: selectedNode.data.retry_policy?.backoff_type || 'constant',
              backoff_base: selectedNode.data.retry_policy?.backoff_base || 1,
              max_backoff: selectedNode.data.retry_policy?.max_backoff || 30,
              on_failure: selectedNode.data.on_failure,
              state_key: selectedNode.data.expectation?.state_key,
              validation: selectedNode.data.expectation?.validation,
              deadline: selectedNode.data.expectation?.deadline || 30,
              condition: (selectedNode.data as unknown as { condition_data?: ConditionNodeData }).condition_data?.condition || '',
              branches: (selectedNode.data as unknown as { condition_data?: ConditionNodeData }).condition_data?.branches || [],
              default_branch: (selectedNode.data as unknown as { condition_data?: ConditionNodeData }).condition_data?.default_branch || 'false',
              language: (selectedNode.data as unknown as { code_data?: CodeNodeData }).code_data?.language || 'javascript',
              code: (selectedNode.data as unknown as { code_data?: CodeNodeData }).code_data?.code || '',
            }}
            onFinish={saveNodeConfig}
          >
            <Form.Item name="label" label="节点名称" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="task" label="任务函数名" rules={[{ required: true }]}>
              <Input placeholder="对应后端函数名" />
            </Form.Item>
            <Form.Item name="skills" label="所需技能">
              <Select mode="tags" placeholder="输入技能标签" />
            </Form.Item>

            {/* 条件分支配置 */}
            {selectedNode.data.variant === 'condition' && (
              <>
                <Divider plain style={{ borderColor: '#722ed1' }}>条件分支配置</Divider>
                <Form.Item name="condition" label="条件表达式">
                  <Input.TextArea rows={2} placeholder="JS 表达式，如 {{input.value}} > 10" />
                </Form.Item>
                <Alert
                  message="引用变量语法"
                  description={<Text code>{`{{variable_name}}`}</Text>}
                  type="info"
                  showIcon
                  style={{ marginBottom: 12 }}
                />
              </>
            )}

            {/* 代码执行节点配置 */}
            {selectedNode.data.variant === 'code' && (
              <>
                <Divider plain style={{ borderColor: '#f5222d' }}>代码编辑器</Divider>
                <Form.Item name="language" label="编程语言">
                  <Select>
                    <Select.Option value="javascript">JavaScript</Select.Option>
                    <Select.Option value="python">Python</Select.Option>
                  </Select>
                </Form.Item>
                <Form.Item name="code" label="代码">
                  <TextArea
                    rows={12}
                    style={{
                      fontFamily: 'monospace',
                      fontSize: 13,
                      lineHeight: 1.5,
                      backgroundColor: '#1e1e1e',
                      color: '#d4d4d4',
                      border: '1px solid #333',
                    }}
                    placeholder="// 在此编写代码"
                  />
                </Form.Item>
                <Alert
                  message="输入变量"
                  description={
                    <span>
                      使用 <Text code>input.xxx</Text> 访问上游节点输出。
                      JavaScript 返回对象，Python 返回字典。
                    </span>
                  }
                  type="info"
                  showIcon
                  style={{ marginBottom: 12 }}
                />
              </>
            )}

            <Divider plain>期望输出</Divider>
            <Form.Item name="state_key" label="状态键 (state_key)">
              <Input placeholder="黑板存储键名" />
            </Form.Item>
            <Form.Item name="validation" label="验证表达式">
              <Input placeholder="Python 风格表达式" />
            </Form.Item>
            <Form.Item name="deadline" label="超时时间 (秒)">
              <InputNumber min={1} max={3600} style={{ width: '100%' }} />
            </Form.Item>

            <Divider plain>重试策略</Divider>
            <Form.Item name="max_attempts" label="最大重试次数">
              <InputNumber min={1} max={10} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="backoff_type" label="退避类型">
              <Select options={[
                { value: 'constant', label: '固定' },
                { value: 'exponential', label: '指数' },
              ]} />
            </Form.Item>
            <Form.Item name="backoff_base" label="基础延迟 (秒)">
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="max_backoff" label="最大延迟 (秒)">
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>

            <Divider plain>失败处理</Divider>
            <Form.Item name="on_failure" label="失败时">
              <Select allowClear placeholder="默认中止" options={[
                { value: 'abort', label: '中止工作流' },
                { value: 'skip', label: '跳过继续' },
              ]} />
            </Form.Item>

            <Form.Item>
              <Button type="primary" htmlType="submit" block>保存配置</Button>
            </Form.Item>
          </Form>
        )}
      </Drawer>
    </div>
  );
}
