import { useState, useCallback, useMemo } from 'react';
import {
  Table, Tag, Button, Space, Drawer, Form, Input, Select, Slider,
  Progress, Radio, Tooltip, Popconfirm, Collapse, Empty, Card, Row, Col, Dropdown, App, Tabs, Upload,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined, StopOutlined, PauseCircleOutlined, EyeOutlined,
  SearchOutlined, AppstoreOutlined, UnorderedListOutlined,
  ThunderboltOutlined, LinkOutlined, ApiOutlined, DeleteOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
  UploadOutlined, CodeOutlined, CloudServerOutlined, SendOutlined,
} from '@ant-design/icons';
import { useEngineStore } from '@/store/useEngineStore';
import type { Capability, CapabilitySource } from '@/types';

// ========== 简约头像组件 ==========
function AgentAvatar({ name, size = 36, color = '#6366f1' }: { name: string; size?: number; color?: string }) {
  const initial = (name || '?')[0].toUpperCase();
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" style={{ flexShrink: 0 }}>
      <circle cx={18} cy={18} r={18} fill={color} opacity={0.12} />
      <circle cx={18} cy={18} r={16} fill="none" stroke={color} strokeWidth={1.5} opacity={0.35} />
      <text x={18} y={18} textAnchor="middle" dominantBaseline="central"
        fill={color} fontSize={16} fontWeight={600} fontFamily="system-ui, sans-serif">
        {initial}
      </text>
    </svg>
  );
}

const SKILL_COLORS: Record<string, string> = {
  // 🔍 搜索与检索
  search: '#1677ff', web: '#1677ff', retrieval: '#1677ff', crawling: '#1677ff', scraping: '#1677ff',
  // 📝 NLP 与文本
  nlp: '#722ed1', text_analysis: '#722ed1', summarization: '#722ed1', generate: '#722ed1',
  translation: '#a0d911', sentiment: '#722ed1', extraction: '#722ed1', chatbot: '#722ed1',
  // 🖼️ 视觉与图像
  image_processing: '#eb2f96', ocr: '#eb2f96', classification: '#eb2f96', object_detection: '#eb2f96',
  face_recognition: '#eb2f96', image_generation: '#eb2f96', video_analysis: '#eb2f96',
  // 📊 数据与分析
  data_analysis: '#13c2c2', visualization: '#13c2c2', reporting: '#13c2c2', data_processing: '#52c41a',
  preprocessing: '#52c41a', feature_engineering: '#13c2c2', forecasting: '#13c2c2', statistics: '#13c2c2',
  // 🧠 AI 与推理
  llm: '#2f54eb', reasoning: '#2f54eb', decision: '#2f54eb', planning: '#fa8c16', decomposition: '#fa8c16',
  analysis: '#fa8c16', thinking: '#2f54eb', problem_solving: '#fa8c16',
  // 🔐 安全与合规
  security: '#fa541c', audit: '#fa541c', vulnerability_scan: '#fa541c', threat_detection: '#fa541c',
  compliance: '#fa541c', encryption: '#fa541c',
  // 💻 开发与工程
  code_generation: '#f5222d', code_review: '#f5222d', testing: '#fa541c', evaluation: '#fa541c',
  debugging: '#f5222d', documentation: '#f5222d', deployment: '#f5222d',
  // 📐 ML 与训练
  ml: '#f5222d', training: '#f5222d', embedding: '#a0d911', ranking: '#a0d911',
  fine_tuning: '#f5222d', model_evaluation: '#f5222d', reinforcement_learning: '#f5222d',
  // 🌐 集成与通信
  api: '#faad14', integration: '#faad14', notification: '#faad14', webhook: '#faad14',
  // 🔧 工具与自动化
  file_io: '#096dd9', database: '#096dd9', workflow: '#096dd9', automation: '#096dd9',
  scheduling: '#096dd9', monitoring: '#096dd9',
};

const SUGGESTED_SKILLS = [
  // 搜索与信息获取
  'search', 'web', 'retrieval', 'crawling', 'scraping',
  // NLP 与文本处理
  'nlp', 'text_analysis', 'summarization', 'translation', 'sentiment', 'extraction', 'chatbot', 'generate',
  // 视觉与图像
  'image_processing', 'ocr', 'classification', 'object_detection', 'face_recognition', 'image_generation',
  // 数据分析
  'data_analysis', 'visualization', 'reporting', 'data_processing', 'preprocessing', 'feature_engineering', 'forecasting', 'statistics',
  // AI 推理与规划
  'llm', 'reasoning', 'decision', 'planning', 'decomposition', 'analysis', 'thinking', 'problem_solving',
  // 安全与合规
  'security', 'audit', 'vulnerability_scan', 'threat_detection', 'compliance', 'encryption',
  // 开发与工程
  'code_generation', 'code_review', 'testing', 'evaluation', 'debugging', 'documentation', 'deployment',
  // ML 与训练
  'ml', 'training', 'embedding', 'ranking', 'fine_tuning', 'model_evaluation', 'reinforcement_learning',
  // 集成与通信
  'api', 'integration', 'notification', 'webhook',
  // 工具与自动化
  'file_io', 'database', 'workflow', 'automation', 'scheduling', 'monitoring',
];

const STATUS_CONFIG: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  starting: { color: '#1677ff', label: '启动中', icon: <ThunderboltOutlined /> },
  running: { color: '#52c41a', label: '运行中', icon: <CheckCircleOutlined /> },
  draining: { color: '#fa8c16', label: '排水', icon: <PauseCircleOutlined /> },
  stopped: { color: '#d9d9d9', label: '已停止', icon: <StopOutlined /> },
};

function agentColor(agent: Capability): string {
  const s = agent.skills[0] || '';
  return SKILL_COLORS[s] || '#6366f1';
}

export default function AgentsPage() {
  const engine = useEngineStore().getEngine();
  const { message } = App.useApp();
  const [agents, setAgents] = useState<Capability[]>(() => engine.getAgents());
  const [search, setSearch] = useState('');
  const [viewMode, setViewMode] = useState<'table' | 'card'>('table');
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Capability | null>(null);
  const [detailAgent, setDetailAgent] = useState<Capability | null>(null);
  const [form] = Form.useForm();
  const [capSource, setCapSource] = useState<CapabilitySource>('preset');

  const refresh = useCallback(() => setAgents(engine.getAgents()), [engine]);

  const filteredAgents = useMemo(() => {
    if (!search) return agents;
    const q = search.toLowerCase();
    return agents.filter(a =>
      a.agent_id.toLowerCase().includes(q) ||
      a.display_name.toLowerCase().includes(q) ||
      a.skills.some(s => s.toLowerCase().includes(q)) ||
      (a.description || '').toLowerCase().includes(q)
    );
  }, [agents, search]);

  // ========== 批量操作 ==========
  const handleBatchDrain = () => {
    selectedRowKeys.forEach(id => engine.drainAgent(id));
    refresh();
    setSelectedRowKeys([]);
    message.info(`已排水 ${selectedRowKeys.length} 个 Agent`);
  };
  const handleBatchStop = () => {
    selectedRowKeys.forEach(id => engine.unregisterAgent(id));
    refresh();
    setSelectedRowKeys([]);
    message.info(`已注销 ${selectedRowKeys.length} 个 Agent`);
  };
  const handleDelete = (id: string) => {
    engine.unregisterAgent(id);
    refresh();
    message.info(`Agent ${id} 已删除`);
  };

  // ========== 新建/编辑 ==========
  const openCreateForm = () => {
    setEditingAgent(null);
    form.resetFields();
    form.setFieldsValue({ weight: 1, model_enabled: false });
    setFormOpen(true);
  };
  const openEditForm = (agent: Capability) => {
    setEditingAgent(agent);
    form.setFieldsValue({
      agent_id: agent.agent_id,
      display_name: agent.display_name,
      skills: agent.skills,
      read_keys: agent.read_keys.join(', '),
      write_keys: agent.write_keys.join(', '),
      weight: agent.weight,
      task_handler: agent.task_handler,
      description: agent.description,
      model_enabled: !!agent.model_config,
      model_provider: agent.model_config?.provider || 'openai',
      model_name: agent.model_config?.model_name || '',
      system_prompt: agent.model_config?.system_prompt || '',
      temperature: agent.model_config?.temperature ?? 0.7,
      tools: agent.model_config?.tools?.join(', ') || '',
    });
    setFormOpen(true);
  };

  const handleFormSubmit = useCallback(() => {
    form.validateFields().then((values: Record<string, any>) => {
      const capData: Capability = {
        agent_id: values.agent_id,
        display_name: values.display_name || values.agent_id,
        description: values.description || '',
        icon: '',
        skills: values.skills || [],
        load: editingAgent?.load ?? 0,
        history: editingAgent?.history ?? [],
        load_history: editingAgent?.load_history ?? [],
        recent_tasks: editingAgent?.recent_tasks ?? [],
        read_keys: values.read_keys ? values.read_keys.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
        write_keys: values.write_keys ? values.write_keys.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
        state: editingAgent?.state ?? 'running',
        weight: values.weight ?? 1,
        pending_tasks: editingAgent?.pending_tasks ?? 0,
        task_handler: values.task_handler || '',
        last_heartbeat: Date.now() / 1000,
      };

      if (values.model_enabled && values.model_name) {
        capData.model_config = {
          provider: values.model_provider || 'openai',
          model_name: values.model_name,
          system_prompt: values.system_prompt || '',
          tools: values.tools ? values.tools.split(',').map((t: string) => t.trim()).filter(Boolean) : [],
          temperature: values.temperature ?? 0.7,
        };
      }

      if (editingAgent) {
        engine.unregisterAgent(editingAgent.agent_id);
        engine.registerAgent(capData);
        message.success(`Agent ${capData.agent_id} 已更新`);
      } else {
        engine.registerAgent(capData);
        message.success(`Agent ${capData.agent_id} 已注册`);
      }
      refresh();
      setFormOpen(false);
      form.resetFields();
      setEditingAgent(null);
    }).catch(() => { });
  }, [engine, refresh, form, editingAgent]);

  // ========== 表格列 ==========
  const columns: ColumnsType<Capability> = [
    { title: 'Agent ID', dataIndex: 'agent_id', key: 'agent_id', width: 160, ellipsis: true,
      sorter: (a, b) => a.agent_id.localeCompare(b.agent_id),
    },
    {
      title: '显示名称', key: 'display_name', width: 160,
      render: (_: unknown, r: Capability) => (
        <Space>
          <AgentAvatar name={r.display_name} size={28} color={agentColor(r)} />
          <span>{r.display_name}</span>
        </Space>
      ),
    },
    {
      title: '技能', dataIndex: 'skills', key: 'skills', width: 200,
      render: (skills: string[]) => (
        <Space size={4} wrap>
          {skills.map(s => <Tag key={s} color={SKILL_COLORS[s] || 'default'}>{s}</Tag>)}
        </Space>
      ),
    },
    {
      title: '状态', dataIndex: 'state', key: 'state', width: 100,
      render: (state: string) => {
        const cfg = STATUS_CONFIG[state];
        return (
          <Space size={4}>
            <span style={{
              display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
              background: cfg.color,
              animation: state === 'running' ? 'pulse 1.5s infinite' : undefined,
            }} />
            <Tag color={cfg.color}>{cfg.label}</Tag>
          </Space>
        );
      },
    },
    {
      title: '负载', dataIndex: 'load', key: 'load', width: 140,
      sorter: (a, b) => a.load - b.load,
      render: (load: number) => {
        const pct = Math.min(load * 20, 100);
        const color = pct > 80 ? '#ff4d4f' : pct > 50 ? '#fa8c16' : '#52c41a';
        return <Progress percent={pct} size="small" strokeColor={color} />;
      },
    },
    { title: '排队', dataIndex: 'pending_tasks', key: 'pending_tasks', width: 70, sorter: (a, b) => a.pending_tasks - b.pending_tasks },
    { title: '权重', dataIndex: 'weight', key: 'weight', width: 70, sorter: (a, b) => a.weight - b.weight },
    {
      title: '操作', key: 'actions', width: 220, fixed: 'right',
      render: (_: unknown, r: Capability) => (
        <Space size="small">
          <Button size="small" icon={<EyeOutlined />} onClick={() => setDetailAgent(r)}>详情</Button>
          <Button size="small" icon={<PauseCircleOutlined />}
            onClick={() => { engine.drainAgent(r.agent_id); refresh(); }}
            disabled={r.state !== 'running'}>排水</Button>
          <Button size="small" danger icon={<StopOutlined />}
            onClick={() => { engine.unregisterAgent(r.agent_id); refresh(); }}>注销</Button>
        </Space>
      ),
    },
  ];

  // ========== 渲染 ==========
  const isEmpty = agents.length === 0;

  return (
    <div>
      {/* 顶部操作栏 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ margin: 0 }}>Agent 管理</h3>
        <Space>
          <Input
            placeholder="搜索 Agent ID / 名称 / 技能..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={e => setSearch(e.target.value)}
            allowClear
            style={{ width: 260 }}
          />
          <Radio.Group value={viewMode} onChange={e => setViewMode(e.target.value)} size="small">
            <Tooltip title="表格视图"><Radio.Button value="table"><UnorderedListOutlined /></Radio.Button></Tooltip>
            <Tooltip title="卡片视图"><Radio.Button value="card"><AppstoreOutlined /></Radio.Button></Tooltip>
          </Radio.Group>
          {selectedRowKeys.length > 0 && (
            <Dropdown menu={{
              items: [
                { key: 'drain', icon: <PauseCircleOutlined />, label: `批量排水 (${selectedRowKeys.length})`, onClick: handleBatchDrain },
                { key: 'stop', icon: <StopOutlined />, label: `批量停止 (${selectedRowKeys.length})`, onClick: handleBatchStop, danger: true },
              ],
            }}>
              <Button>批量操作 ({selectedRowKeys.length})</Button>
            </Dropdown>
          )}
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateForm}>新建 Agent</Button>
        </Space>
      </div>

      {/* 空状态 */}
      {isEmpty && (
        <Card style={{ textAlign: 'center', padding: 48 }}>
          <Empty
            image={<AgentAvatar name="?" size={64} color="#d9d9d9" />}
            description="还没有注册任何 AI Agent"
          >
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateForm}>注册你的第一个 AI Agent</Button>
          </Empty>
        </Card>
      )}

      {/* 表格视图 */}
      {!isEmpty && viewMode === 'table' && (
        <Table<Capability>
          columns={columns}
          dataSource={filteredAgents}
          rowKey="agent_id"
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys as string[]),
          }}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: t => `共 ${t} 个 Agent` }}
          size="middle"
          scroll={{ x: 1100 }}
        />
      )}

      {/* 卡片视图 */}
      {!isEmpty && viewMode === 'card' && (
        <Row gutter={[16, 16]}>
          {filteredAgents.map(a => {
            const statusCfg = STATUS_CONFIG[a.state];
            const loadPct = Math.min(a.load * 20, 100);
            const loadColor = loadPct > 80 ? '#ff4d4f' : loadPct > 50 ? '#fa8c16' : '#52c41a';
            return (
              <Col xs={24} sm={12} lg={8} xl={6} key={a.agent_id}>
                <Card
                  hoverable
                  onClick={() => setDetailAgent(a)}
                  actions={[
                    <Tooltip title="详情" key="detail"><EyeOutlined /></Tooltip>,
                    <Tooltip title="排水" key="drain"><PauseCircleOutlined onClick={e => { e.stopPropagation(); engine.drainAgent(a.agent_id); refresh(); }} /></Tooltip>,
                    <Popconfirm title="确定删除该 Agent？" onConfirm={e => { e?.stopPropagation(); handleDelete(a.agent_id); }} onCancel={e => e?.stopPropagation()} key="delete">
                      <DeleteOutlined onClick={e => e.stopPropagation()} />
                    </Popconfirm>,
                  ]}
                >
                  <div style={{ textAlign: 'center' }}>
                    <AgentAvatar name={a.display_name} size={44} color={agentColor(a)} />
                    <div style={{ fontWeight: 600, fontSize: 15, marginTop: 8 }}>{a.display_name}</div>
                    <div style={{ color: '#888', fontSize: 12, marginTop: 2 }}>{a.agent_id}</div>
                    <div style={{ marginTop: 8 }}>
                      <span style={{
                        display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                        background: statusCfg.color, marginRight: 4,
                        animation: a.state === 'running' ? 'pulse 1.5s infinite' : undefined,
                      }} />
                      <span style={{ fontSize: 12, color: statusCfg.color }}>{statusCfg.label}</span>
                    </div>
                    <div style={{ marginTop: 12 }}>
                      <Progress type="circle" percent={loadPct} size={64} strokeColor={loadColor} format={() => `${a.load}`} />
                    </div>
                    <div style={{ marginTop: 8 }}>
                      <Space size={4} wrap style={{ justifyContent: 'center' }}>
                        {a.skills.map(s => <Tag key={s} color={SKILL_COLORS[s] || 'default'}>{s}</Tag>)}
                      </Space>
                    </div>
                  </div>
                </Card>
              </Col>
            );
          })}
        </Row>
      )}

      {/* ========== 新建/编辑 Agent 抽屉 ========== */}
      <Drawer
        title={editingAgent ? `编辑 Agent: ${editingAgent.agent_id}` : '新建 AI Agent'}
        open={formOpen}
        onClose={() => { setFormOpen(false); setEditingAgent(null); form.resetFields(); }}
        width={480}
        extra={
          <Space>
            <Tooltip title="测试连接 (真实模式)"><Button icon={<ApiOutlined />} disabled>测试连接</Button></Tooltip>
            <Button onClick={() => { setFormOpen(false); setEditingAgent(null); form.resetFields(); }}>取消</Button>
            <Button type="primary" onClick={handleFormSubmit}>{editingAgent ? '保存' : '注册'}</Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical" size="middle">
          <Form.Item name="agent_id" label="Agent ID" rules={[{ required: true, message: '请输入唯一 Agent ID' }]}>
            <Input placeholder="例如: search-agent-v1" disabled={!!editingAgent} />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称">
            <Input placeholder="例如: 搜索引擎助手" />
          </Form.Item>

          {/* 自动生成头像预览 */}
          <Form.Item label="头像" tooltip="根据显示名称和技能自动生成">
            <Form.Item noStyle shouldUpdate>
              {({ getFieldValue }) => {
                const name = getFieldValue('display_name') || getFieldValue('agent_id') || 'Agent';
                const skills = (getFieldValue('skills') || []) as string[];
                const color = skills.length > 0 ? (SKILL_COLORS[skills[0]] || '#6366f1') : '#6366f1';
                return (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <AgentAvatar name={name} size={40} color={color} />
                    <span style={{ fontSize: 12, color: '#888' }}>根据名称和首项技能自动配色</span>
                  </div>
                );
              }}
            </Form.Item>
          </Form.Item>

          <Form.Item name="skills" label="技能标签" rules={[{ required: true, message: '请选择至少一个技能' }]}>
            <Select mode="tags" placeholder="输入技能后回车添加" tokenSeparators={[',']} style={{ width: '100%' }}
              options={SUGGESTED_SKILLS.map(s => ({ value: s, label: s }))} />
          </Form.Item>
          <div style={{ marginTop: -16, marginBottom: 16 }}>
            <span style={{ fontSize: 11, color: '#888' }}>建议技能: </span>
            {SUGGESTED_SKILLS.slice(0, 6).map(s => (
              <Tag key={s} style={{ cursor: 'pointer' }}
                onClick={() => {
                  const cur = (form.getFieldValue('skills') || []) as string[];
                  if (!cur.includes(s)) form.setFieldValue('skills', [...cur, s]);
                }}>{s}</Tag>
            ))}
          </div>

          <Form.Item name="read_keys" label="可读黑板键" tooltip="允许从黑板读取的键白名单，逗号分隔">
            <Input placeholder="query, context" />
          </Form.Item>
          <Form.Item name="write_keys" label="可写黑板键" tooltip="允许写入黑板的键白名单，逗号分隔">
            <Input placeholder="search_results, error_log" />
          </Form.Item>

          <Form.Item name="weight" label={<span>权重 <span style={{ fontSize: 11, color: '#888' }}>(0.1 - 10)</span></span>} initialValue={1}>
            <Slider min={0.1} max={10} step={0.1} marks={{ 0.1: '0.1', 1: '1', 5: '5', 10: '10' }}
              tooltip={{ formatter: v => `${v} ${v! > 5 ? '(高性能)' : v! < 1 ? '(低功耗)' : '(标准)'}` }} />
          </Form.Item>

          {/* ========== 能力来源 ========== */}
          <Form.Item label="能力来源">
            <Tabs
              activeKey={capSource}
              onChange={(k) => setCapSource(k as CapabilitySource)}
              size="small"
              items={[
                {
                  key: 'preset',
                  label: <span><CloudServerOutlined /> 系统预置</span>,
                  children: (
                    <Form.Item name="task_handler" style={{ marginBottom: 0 }}
                      tooltip="选择系统预置的后端协程函数">
                      <Select allowClear showSearch placeholder="选择预置处理器..."
                        filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}
                        options={[
                          { value: '', label: '无 (自动匹配)' },
                          { key: 'sys', label: '▸ 系统预置', options: [
                            { value: 'nlp_processor', label: 'nlp_processor' },
                            { value: 'image_processor', label: 'image_processor' },
                            { value: 'data_analyzer', label: 'data_analyzer' },
                          ]},
                        ]} />
                    </Form.Item>
                  ),
                },
                {
                  key: 'external_service',
                  label: <span><ApiOutlined /> 外部服务调用</span>,
                  children: (
                    <>
                      <Form.Item name="svc_name" label="服务名称" rules={[{ required: capSource === 'external_service', message: '请输入服务名称' }]}>
                        <Input placeholder="例如: Bing搜索" />
                      </Form.Item>
                      <Form.Item name="svc_method" label="请求方法" initialValue="GET">
                        <Select options={['GET', 'POST', 'PUT', 'DELETE'].map(v => ({ value: v, label: v }))} />
                      </Form.Item>
                      <Form.Item name="svc_url" label="URL" rules={[{ required: capSource === 'external_service', message: '请输入 API URL' }]}>
                        <Input placeholder="https://api.example.com/search" />
                      </Form.Item>
                      <Form.Item name="svc_timeout" label="超时 (秒)" initialValue={5}>
                        <Input type="number" min={1} max={30} />
                      </Form.Item>
                      <Form.Item name="svc_body" label="请求体 (JSON, 支持 {{payload.xx}} 模板)">
                        <Input.TextArea rows={4} placeholder='{"query": "{{payload.query}}"}' style={{ fontFamily: 'monospace' }} />
                      </Form.Item>
                      <Form.Item name="svc_output" label="输出映射 (JSONPath)" tooltip="提取响应中的指定字段，留空返回完整响应">
                        <Input placeholder="$.data.results" />
                      </Form.Item>
                      <Form.Item name="svc_bbkey" label="黑板写入键" tooltip="提取后写入黑板的键名">
                        <Input placeholder="results" />
                      </Form.Item>
                      <Button icon={<SendOutlined />} style={{ width: '100%' }} disabled>
                        测试调用 (需真实后端)
                      </Button>
                    </>
                  ),
                },
                {
                  key: 'upload',
                  label: <span><UploadOutlined /> 上传代码文件</span>,
                  children: (
                    <>
                      <Form.Item name="upload_handler_name" label="处理器名称">
                        <Input placeholder="自动从文件名提取" />
                      </Form.Item>
                      <Upload.Dragger
                        accept=".py"
                        maxCount={1}
                        beforeUpload={() => false}
                        style={{ marginBottom: 16 }}
                      >
                        <p><UploadOutlined style={{ fontSize: 24 }} /></p>
                        <p style={{ fontSize: 12 }}>点击或拖拽上传 .py 文件</p>
                      </Upload.Dragger>
                      <div style={{
                        background: '#1e1e1e', borderRadius: 6, padding: 12,
                        color: '#d4d4d4', fontFamily: 'monospace', fontSize: 12,
                        minHeight: 80, display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                        <span style={{ color: '#6a9955' }}># 上传文件后此处显示代码预览</span>
                      </div>
                      <Button style={{ width: '100%', marginTop: 12 }} disabled>代码安全检查 (需真实后端)</Button>
                    </>
                  ),
                },
                {
                  key: 'online_edit',
                  label: <span><CodeOutlined /> 在线编写</span>,
                  children: (
                    <>
                      <Form.Item name="edit_handler_name" label="函数名称">
                        <Input placeholder="例如: my_custom_handler" />
                      </Form.Item>
                      <Select
                        placeholder="选择代码模板..."
                        style={{ marginBottom: 12 }}
                        options={[
                          { value: 'blank', label: '空白模板' },
                          { value: 'search_summary', label: '搜索 + 摘要' },
                          { value: 'llm_call', label: 'LLM 调用' },
                        ]}
                      />
                      <div style={{
                        background: '#1e1e1e', borderRadius: 6, overflow: 'hidden',
                        border: '1px solid #333',
                      }}>
                        <div style={{ padding: '4px 12px', background: '#2d2d2d', fontSize: 11, color: '#888' }}>
                          handler.py
                        </div>
                        <Input.TextArea
                          rows={8}
                          style={{
                            background: '#1e1e1e', color: '#d4d4d4', fontFamily: 'Consolas, Monaco, monospace',
                            fontSize: 12, border: 'none', resize: 'vertical',
                          }}
                          placeholder={`async def handler(ecm, blackboard):\n    """自定义任务处理器"""\n    query = ecm.payload.get("query")\n    # TODO: 实现逻辑\n    result = {"output": query}\n    await blackboard.put("result", result)\n    return result`}
                        />
                      </div>
                    </>
                  ),
                },
              ]}
            />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="说明 Agent 的用途和能力..." />
          </Form.Item>

          {/* ========== AI 模型绑定 ========== */}
          <Collapse
            ghost
            items={[{
              key: 'model',
              label: <span><LinkOutlined /> AI 模型绑定 (高级)</span>,
              children: (
                <>
                  <Form.Item name="model_enabled" valuePropName="checked" style={{ marginBottom: 8 }}>
                    <Radio.Group>
                      <Radio value={false}>不使用</Radio>
                      <Radio value={true}>绑定大模型</Radio>
                    </Radio.Group>
                  </Form.Item>
                  <Form.Item noStyle shouldUpdate={(prev, cur) => prev.model_enabled !== cur.model_enabled}>
                    {({ getFieldValue }) => {
                      const enabled = getFieldValue('model_enabled');
                      if (!enabled) return null;
                      return (
                        <>
                          <Form.Item name="model_provider" label="模型提供商">
                            <Select options={[
                              { value: 'openai', label: 'OpenAI' },
                              { value: 'anthropic', label: 'Anthropic' },
                              { value: 'ollama', label: 'Ollama (本地)' },
                              { value: 'custom', label: '自定义' },
                            ]} />
                          </Form.Item>
                          <Form.Item name="model_name" label="模型名称" rules={[{ required: enabled, message: '请输入模型名称' }]}>
                            <Input placeholder="gpt-4o / claude-3.5-sonnet / ..." />
                          </Form.Item>
                          <Form.Item name="system_prompt" label="系统提示词">
                            <Input.TextArea rows={3} placeholder="定义 Agent 的角色和行为..." />
                          </Form.Item>
                          <Form.Item name="temperature" label="温度 (0-2)">
                            <Slider min={0} max={2} step={0.1} marks={{ 0: '0', 0.7: '0.7', 1: '1', 2: '2' }} />
                          </Form.Item>
                          <Form.Item name="tools" label="工具列表" tooltip="Agent 可调用的外部工具，逗号分隔">
                            <Input placeholder="web_search, calculator, file_read" />
                          </Form.Item>
                        </>
                      );
                    }}
                  </Form.Item>
                </>
              ),
            }]}
          />
        </Form>
      </Drawer>

      {/* ========== Agent 详情抽屉 ========== */}
      <Drawer
        title={
          <Space>
            <AgentAvatar name={detailAgent?.display_name || '?'} size={32} color={detailAgent ? agentColor(detailAgent) : '#6366f1'} />
            <span>{detailAgent?.display_name}</span>
          </Space>
        }
        open={!!detailAgent}
        onClose={() => setDetailAgent(null)}
        width={500}
        extra={detailAgent && (
          <Space>
            <Button size="small" onClick={() => { openEditForm(detailAgent); setDetailAgent(null); }}>编辑</Button>
            <Button size="small" icon={<PauseCircleOutlined />}
              onClick={() => { engine.drainAgent(detailAgent.agent_id); refresh(); setDetailAgent(null); }}
              disabled={detailAgent.state !== 'running'}>排水</Button>
          </Space>
        )}
      >
        {detailAgent && (() => {
          const cfg = STATUS_CONFIG[detailAgent.state];
          const loadPct = Math.min(detailAgent.load * 20, 100);
          const loadColor = loadPct > 80 ? '#ff4d4f' : loadPct > 50 ? '#fa8c16' : '#52c41a';

          return (
            <div>
              {/* 基本状态 */}
              <Card size="small" style={{ marginBottom: 16 }}>
                <Row gutter={[16, 12]}>
                  <Col span={12}>
                    <div style={{ color: '#888', fontSize: 12 }}>Agent ID</div>
                    <div style={{ fontWeight: 500 }}>{detailAgent.agent_id}</div>
                  </Col>
                  <Col span={12}>
                    <div style={{ color: '#888', fontSize: 12 }}>状态</div>
                    <Space size={4}>
                      <span style={{
                        display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: cfg.color,
                        animation: detailAgent.state === 'running' ? 'pulse 1.5s infinite' : undefined,
                      }} />
                      <Tag color={cfg.color}>{cfg.label}</Tag>
                    </Space>
                  </Col>
                  <Col span={12}>
                    <div style={{ color: '#888', fontSize: 12 }}>负载</div>
                    <Progress percent={loadPct} size="small" strokeColor={loadColor} />
                  </Col>
                  <Col span={12}>
                    <div style={{ color: '#888', fontSize: 12 }}>排队任务</div>
                    <div style={{ fontWeight: 500 }}>{detailAgent.pending_tasks}</div>
                  </Col>
                  <Col span={12}>
                    <div style={{ color: '#888', fontSize: 12 }}>权重</div>
                    <div style={{ fontWeight: 500 }}>{detailAgent.weight}</div>
                  </Col>
                  <Col span={12}>
                    <div style={{ color: '#888', fontSize: 12 }}>最后心跳</div>
                    <div style={{ fontWeight: 500, fontSize: 12 }}>
                      {new Date(detailAgent.last_heartbeat * 1000).toLocaleString()}
                    </div>
                  </Col>
                </Row>
              </Card>

              {/* 技能标签 */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>技能标签</div>
                <Space size={4} wrap>
                  {detailAgent.skills.map(s => <Tag key={s} color={SKILL_COLORS[s] || 'default'}>{s}</Tag>)}
                </Space>
              </div>

              {/* 黑板权限 */}
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={12}>
                  <div style={{ color: '#888', fontSize: 12 }}>可读黑板键</div>
                  <div>{detailAgent.read_keys.length > 0 ? detailAgent.read_keys.join(', ') : <span style={{ color: '#ccc' }}>无限制</span>}</div>
                </Col>
                <Col span={12}>
                  <div style={{ color: '#888', fontSize: 12 }}>可写黑板键</div>
                  <div>{detailAgent.write_keys.length > 0 ? detailAgent.write_keys.join(', ') : <span style={{ color: '#ccc' }}>无限制</span>}</div>
                </Col>
              </Row>

              {detailAgent.task_handler && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ color: '#888', fontSize: 12 }}>任务处理器</div>
                  <Tag color="blue">{detailAgent.task_handler}</Tag>
                </div>
              )}

              {detailAgent.description && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ color: '#888', fontSize: 12 }}>描述</div>
                  <div>{detailAgent.description}</div>
                </div>
              )}

              {/* 模型配置 */}
              {detailAgent.model_config && (
                <Card title="AI 模型配置" size="small" style={{ marginBottom: 16 }}>
                  <Row gutter={[16, 8]}>
                    <Col span={12}><span style={{ color: '#888' }}>提供商: </span>{detailAgent.model_config.provider}</Col>
                    <Col span={12}><span style={{ color: '#888' }}>模型: </span>{detailAgent.model_config.model_name}</Col>
                    {detailAgent.model_config.system_prompt && (
                      <Col span={24}><span style={{ color: '#888' }}>提示词: </span><span style={{ fontSize: 12 }}>{detailAgent.model_config.system_prompt}</span></Col>
                    )}
                    {detailAgent.model_config.tools && detailAgent.model_config.tools.length > 0 && (
                      <Col span={24}><span style={{ color: '#888' }}>工具: </span><Space size={4}>{detailAgent.model_config.tools.map(t => <Tag key={t}>{t}</Tag>)}</Space></Col>
                    )}
                  </Row>
                </Card>
              )}

              {/* 负载历史 */}
              <Card title="负载历史 (最近 1 小时)" size="small" style={{ marginBottom: 16 }}>
                {detailAgent.load_history.length > 0 ? (
                  <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 60, paddingTop: 8 }}>
                    {detailAgent.load_history.map((p, i) => (
                      <Tooltip key={i} title={`负载: ${p.load} @ ${new Date(p.time * 1000).toLocaleTimeString()}`}>
                        <div style={{
                          flex: 1, minWidth: 2, background: loadColor, height: `${Math.min(p.load * 10, 100)}%`,
                          borderRadius: '2px 2px 0 0', opacity: 0.8,
                        }} />
                      </Tooltip>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: '#ccc', textAlign: 'center', height: 60, lineHeight: '60px' }}>
                    暂无历史数据，执行任务后自动记录
                  </div>
                )}
              </Card>

              {/* 最近任务 */}
              <Card title="最近任务" size="small">
                {detailAgent.recent_tasks.length > 0 ? (
                  <Table
                    dataSource={detailAgent.recent_tasks.slice().reverse().map((t, i) => ({ ...t, key: i }))}
                    columns={[
                      {
                        title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 110,
                        render: (v: number) => new Date(v * 1000).toLocaleTimeString(),
                      },
                      { title: '意图ID', dataIndex: 'intent_id', key: 'intent_id', ellipsis: true },
                      {
                        title: '状态', dataIndex: 'status', key: 'status', width: 80,
                        render: (v: string) => (
                          <Space size={4}>
                            {v === 'success' ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                              v === 'failed' ? <CloseCircleOutlined style={{ color: '#ff4d4f' }} /> :
                                <ClockCircleOutlined style={{ color: '#fa8c16' }} />}
                            <span>{v === 'success' ? '成功' : v === 'failed' ? '失败' : '超时'}</span>
                          </Space>
                        ),
                      },
                      {
                        title: '耗时', dataIndex: 'duration', key: 'duration', width: 80,
                        render: (v: number) => `${v.toFixed(2)}s`,
                      },
                    ]}
                    size="small"
                    pagination={{ pageSize: 5 }}
                  />
                ) : (
                  <div style={{ color: '#ccc', textAlign: 'center', padding: 16 }}>暂无任务记录</div>
                )}
              </Card>
            </div>
          );
        })()}
      </Drawer>

      {/* 脉冲动画 */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}