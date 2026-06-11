import { useState, useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ReactFlow, {
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Handle,
  Position,
  type Node,
  type NodeProps,
  type Connection,
  Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Button, Space, Input, Drawer, Form, Tag, Card,
  Typography, Divider, App, Popconfirm, Alert, Switch, Spin,
} from 'antd';
import {
  PlayCircleOutlined, SaveOutlined, FolderOpenOutlined,
  UserOutlined, RobotOutlined, BranchesOutlined,
  TagOutlined, DeleteOutlined, SendOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import type { ChatflowNodeData } from '@/types';
import dbManager from '@/persistence/IndexedDBManager';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { useEngineStore } from '@/store/useEngineStore';
import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';
import { getErrorMessage } from '@/utils/api';
import { executeChatflowWithAgent } from '@/utils/chatflowTopology';

const { Text, Paragraph } = Typography;

// ========== 节点类型颜色映射 ==========
const NODE_COLORS: Record<string, string> = {
  user_input: '#1890ff',
  ai_reply: '#52c41a',
  condition: '#722ed1',
  variable: '#fa8c16',
};

const NODE_LABELS: Record<string, string> = {
  user_input: '用户输入',
  ai_reply: 'AI 回复',
  condition: '条件分支',
  variable: '变量设置',
};

// ========== 自定义 Chatflow 节点 ==========
function ChatflowNode({ data, selected }: NodeProps<ChatflowNodeData>) {
  const color = NODE_COLORS[data.nodeType] || '#6366f1';
  const iconMap: Record<string, JSX.Element> = {
    user_input: <UserOutlined />,
    ai_reply: <RobotOutlined />,
    condition: <BranchesOutlined />,
    variable: <TagOutlined />,
  };

  return (
    <div
      style={{
        background: '#fff',
        border: `2px solid ${selected ? color : '#d9d9d9'}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 180,
        maxWidth: 250,
        boxShadow: selected ? `0 0 8px ${color}40` : '0 1px 3px rgba(0,0,0,0.1)',
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ width: 12, height: 12, background: '#fff', border: `2px solid ${color}`, borderRadius: '50%' }}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ color, fontSize: 14 }}>{iconMap[data.nodeType]}</span>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{data.label}</span>
        <Tag color={color} style={{ marginLeft: 'auto', fontSize: 10, padding: '0 4px' }}>
          {NODE_LABELS[data.nodeType]}
        </Tag>
      </div>
      {data.prompt && (
        <div style={{ fontSize: 12, color: '#666', marginTop: 4, maxHeight: 60, overflow: 'hidden' }}>
          {data.prompt.length > 50 ? data.prompt.slice(0, 50) + '...' : data.prompt}
        </div>
      )}
      {data.variable_mapping && Object.keys(data.variable_mapping).length > 0 && (
        <div style={{ marginTop: 4 }}>
          {Object.entries(data.variable_mapping).map(([k, v]) => (
            <Tag key={k} style={{ fontSize: 10, margin: 1 }}>{k} → {v}</Tag>
          ))}
        </div>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ width: 12, height: 12, background: '#fff', border: `2px solid ${color}`, borderRadius: '50%' }}
      />
    </div>
  );
}

const nodeTypes = {
  chatflowNode: ChatflowNode,
};

// ========== 主页面 ==========
export default function ChatflowPage() {
  const { message } = App.useApp();
  const engineMode = useEngineStore(s => s.mode);
  const runtimeMode = useAgentRuntimeStore(s => s.runtimeMode);
  const agentActive = useAgentRuntimeStore(s => s.agentActive);
  const fetchRuntime = useAgentRuntimeStore(s => s.fetchRuntime);
  const runAgentQuery = useAgentRuntimeStore(s => s.runQuery);
  const planOnly = useAgentRuntimeStore(s => s.planOnly);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node<ChatflowNodeData> | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<{ role: string; content: string; meta?: string }[]>([]);
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

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node<ChatflowNodeData>) => {
      setSelectedNode(node);
      form.setFieldsValue(node.data);
      setDrawerOpen(true);
    },
    [form]
  );

  const addNode = (nodeType: ChatflowNodeData['nodeType']) => {
    const id = `chat_${Date.now()}`;
    const position = {
      x: 100 + Math.random() * 300,
      y: 100 + Math.random() * 200,
    };

    const labels: Record<string, string> = {
      user_input: '用户输入',
      ai_reply: 'AI 回复',
      condition: '条件判断',
      variable: '变量设置',
    };

    const newNode: Node<ChatflowNodeData> = {
      id,
      type: 'chatflowNode',
      position,
      data: {
        label: `${labels[nodeType]} ${nodes.filter((n) => n.type === 'chatflowNode').length + 1}`,
        nodeType,
        prompt: '',
        variable_mapping: {},
        condition: '',
      },
    };

    setNodes((nds) => [...nds, newNode]);
    message.success(`已添加 ${labels[nodeType]} 节点`);
  };

  const deleteNode = (nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    if (selectedNode?.id === nodeId) {
      setDrawerOpen(false);
      setSelectedNode(null);
    }
  };

  const saveNodeChanges = async () => {
    const values = await form.validateFields();
    if (selectedNode) {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === selectedNode.id
            ? { ...n, data: { ...n.data, ...values } }
            : n
        )
      );
      message.success('节点已更新');
      setDrawerOpen(false);
    }
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim()) return;

    const text = chatInput.trim();
    const userMsg = { role: 'user', content: text };
    setChatMessages((prev) => [...prev, userMsg]);
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
          message.warning('执行计划未获批准');
        }
      } catch (e) {
        message.error(getErrorMessage(e));
        setChatMessages((prev) => [
          ...prev,
          { role: 'ai', content: `Agent 调用失败: ${getErrorMessage(e)}` },
        ]);
      } finally {
        setAgentLoading(false);
      }
      return;
    }

    setTimeout(() => {
      const aiMsg = {
        role: 'ai',
        content: `收到您的消息：「${text}」\n\n（模拟模式）开启真实模式并切换 Agent 运行时，将调用 HiveMindApp.run_query。`,
      };
      setChatMessages((prev) => [...prev, aiMsg]);
    }, 300);
  };

  const handlePlanOnlyFromChat = async () => {
    if (!chatInput.trim()) {
      message.warning('请先输入消息');
      return;
    }
    if (!agentAvailable) {
      message.warning('需要真实模式 + Agent 运行时');
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
      message.success('已生成执行计划（未执行）');
    } catch (e) {
      message.error(getErrorMessage(e));
    } finally {
      setAgentLoading(false);
    }
  };

  const clearCanvas = () => {
    setNodes([]);
    setEdges([]);
    setChatMessages([]);
    message.info('画布已清空');
  };

  // 手动保存 Chatflow
  const saveChatflow = useCallback(async () => {
    try {
      const chatflowId = useWorkflowStore.getState().currentWorkflowId || 'chatflow_default';
      await dbManager.saveWorkflow({
        id: chatflowId,
        name: `Chatflow ${chatflowId.slice(-6)}`,
        nodes,
        edges,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      });
      message.success('Chatflow 已保存');
    } catch {
      message.error('保存失败');
    }
  }, [nodes, edges, message]);

  // 加载 Chatflow
  const loadChatflow = useCallback(async () => {
    try {
      const workflows = await dbManager.getAllWorkflows();
      if (workflows.length > 0) {
        const latest = workflows.sort((a, b) => b.updatedAt - a.updatedAt)[0];
        setNodes(latest.nodes);
        setEdges(latest.edges);
        message.success('已加载上次保存的 Chatflow');
      } else {
        message.info('暂无保存的 Chatflow');
      }
    } catch {
      message.error('加载失败');
    }
  }, [setNodes, setEdges, message]);

  const executeChatflow = async () => {
    if (nodes.length === 0) {
      message.warning('请先添加节点');
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
          { role: 'ai', content: finalAnswer || '完成', meta: intentId ? `intent_id: ${intentId}` : undefined },
        ]);
        message.success(`Chatflow 拓扑执行完成 (${steps.length} 步)`);
      } catch (e) {
        message.error(getErrorMessage(e));
      } finally {
        setAgentLoading(false);
      }
      return;
    }
    message.info('Chatflow 执行中...（模拟）');
    setTimeout(() => message.success('Chatflow 执行完成'), 1500);
  };

  const nodeCount = nodes.filter((n) => n.type === 'chatflowNode').length;

  return (
    <div style={{ height: 'calc(100vh - 64px - 24px)', display: 'flex', gap: 16 }}>
      {/* 左侧：画布 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* 工具栏 */}
        <Card size="small" style={{ marginBottom: 12 }}>
          <Space wrap>
            {engineMode === 'real' && (
              <>
                <Tag color={agentAvailable ? 'purple' : 'default'}>
                  {agentAvailable ? 'Agent 已就绪' : 'Core / Agent 未激活'}
                </Tag>
                <Switch
                  checked={useAgentMode}
                  onChange={setUseAgentMode}
                  disabled={!agentAvailable}
                  checkedChildren="Agent"
                  unCheckedChildren="模拟"
                />
              </>
            )}
            <Button
              type="primary"
              icon={<UserOutlined />}
              onClick={() => addNode('user_input')}
            >
              用户输入
            </Button>
            <Button
              icon={<RobotOutlined />}
              onClick={() => addNode('ai_reply')}
            >
              AI 回复
            </Button>
            <Button
              icon={<BranchesOutlined />}
              onClick={() => addNode('condition')}
            >
              条件分支
            </Button>
            <Button
              icon={<TagOutlined />}
              onClick={() => addNode('variable')}
            >
              变量设置
            </Button>
            <Divider type="vertical" />
            <Button
              icon={<SaveOutlined />}
              onClick={saveChatflow}
            >
              保存
            </Button>
            <Button
              icon={<FolderOpenOutlined />}
              onClick={loadChatflow}
            >
              加载
            </Button>
            <Divider type="vertical" />
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={executeChatflow}
              disabled={nodeCount === 0}
            >
              执行
            </Button>
            <Popconfirm title="确定清空画布？" onConfirm={clearCanvas}>
              <Button icon={<DeleteOutlined />} danger>
                清空
              </Button>
            </Popconfirm>
            <Tag style={{ marginLeft: 8 }}>
              节点数: {nodeCount}
            </Tag>
          </Space>
        </Card>

        {/* React Flow 画布 */}
        <div style={{ flex: 1, border: '1px solid #d9d9d9', borderRadius: 8 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
          >
            <Controls />
            <MiniMap />
            <Background gap={16} size={1} />
            <Panel position="top-right">
              <Tag color="blue">点击节点编辑属性</Tag>
            </Panel>
          </ReactFlow>
        </div>
      </div>

      {/* 右侧：对话预览 */}
      <div style={{ width: 380, display: 'flex', flexDirection: 'column' }}>
        <Card
          title={
            <Space>
              <MessageOutlined />
              <span>对话预览</span>
              {agentLoading && <Spin size="small" />}
            </Space>
          }
          size="small"
          extra={
            <Button
              size="small"
              onClick={() => setChatMessages([])}
              disabled={chatMessages.length === 0}
            >
              清空
            </Button>
          }
          style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
          styles={{ body: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 12 } }}
        >
          {agentAvailable && useAgentMode && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 8 }}
              message="发送消息将调用 run_query；可前往编排器导入 plan 或使用 plan-only。"
            />
          )}
          {lastIntentId && (
            <div style={{ marginBottom: 8, fontSize: 12 }}>
              <Link to={`/tracer?intent_id=${encodeURIComponent(lastIntentId)}`}>Tracer</Link>
              {' · '}
              <Link to={`/replay?intent_id=${encodeURIComponent(lastIntentId)}`}>Replay</Link>
            </div>
          )}
          {/* 消息列表 */}
          <div style={{ flex: 1, overflowY: 'auto', marginBottom: 12 }}>
            {chatMessages.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
                <MessageOutlined style={{ fontSize: 32, marginBottom: 8 }} />
                <p>暂无对话消息</p>
                <p style={{ fontSize: 12 }}>发送消息开始测试 Chatflow</p>
              </div>
            ) : (
              chatMessages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    marginBottom: 12,
                  }}
                >
                  <div
                    style={{
                      maxWidth: '80%',
                      padding: '8px 12px',
                      borderRadius: 12,
                      background: msg.role === 'user' ? '#1890ff' : '#f0f0f0',
                      color: msg.role === 'user' ? '#fff' : '#000',
                      fontSize: 13,
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    <Paragraph style={{ margin: 0, color: 'inherit' }}>
                      {msg.content}
                    </Paragraph>
                    {msg.meta && (
                      <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                        {msg.meta}
                      </Text>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* 输入框 */}
          <Space.Compact style={{ width: '100%' }}>
            <Input
              placeholder="输入消息..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onPressEnter={() => void handleSendMessage()}
              allowClear
              disabled={agentLoading}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={() => void handleSendMessage()}
              loading={agentLoading}
            >
              发送
            </Button>
          </Space.Compact>
          {agentAvailable && useAgentMode && (
            <Button
              block
              style={{ marginTop: 8 }}
              icon={<RobotOutlined />}
              onClick={() => void handlePlanOnlyFromChat()}
              loading={agentLoading}
            >
              plan-only（仅规划）
            </Button>
          )}
        </Card>
      </div>

      {/* 节点属性编辑抽屉 */}
      <Drawer
        title="节点属性"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={400}
        extra={
          <Space>
            <Popconfirm title="确定删除此节点？" onConfirm={() => deleteNode(selectedNode?.id ?? '')}>
              <Button danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
            <Button type="primary" icon={<SaveOutlined />} onClick={saveNodeChanges}>
              保存
            </Button>
          </Space>
        }
      >
        {selectedNode && (
          <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
            <Form.Item
              name="label"
              label="节点名称"
              rules={[{ required: true, message: '请输入节点名称' }]}
            >
              <Input />
            </Form.Item>

            {selectedNode.data.nodeType === 'user_input' && (
              <Form.Item name="prompt" label="输入提示">
                <Input.TextArea
                  rows={3}
                  placeholder="例如：请输入您的查询内容"
                />
              </Form.Item>
            )}

            {selectedNode.data.nodeType === 'ai_reply' && (
              <>
                <Form.Item name="prompt" label="回复模板">
                  <Input.TextArea
                    rows={4}
                    placeholder="可以使用 {{variable}} 语法引用变量"
                  />
                </Form.Item>
                <Form.Item label="变量映射">
                  <Typography.Text type="secondary">
                    在 prompt 中使用 {'{{变量名}}'} 引用上游变量
                  </Typography.Text>
                </Form.Item>
              </>
            )}

            {selectedNode.data.nodeType === 'condition' && (
              <Form.Item name="condition" label="条件表达式" extra="支持 JS 表达式，使用 {{变量}} 引用">
                <Input.TextArea
                  rows={3}
                  placeholder="例如：{{score}} > 0.8"
                />
              </Form.Item>
            )}

            {selectedNode.data.nodeType === 'variable' && (
              <Form.Item label="变量提取配置">
                <Typography.Text type="secondary">
                  配置从对话中提取的变量及其映射关系
                </Typography.Text>
              </Form.Item>
            )}
          </Form>
        )}
      </Drawer>
    </div>
  );
}
