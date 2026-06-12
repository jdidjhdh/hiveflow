import { useState, useCallback, useMemo, useEffect } from 'react';
import {
  Table, Tag, Button, Space, Form, Input,
  Progress, Radio, Tooltip, Popconfirm, Empty, Card, Row, Col, Dropdown, App,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined, StopOutlined, PauseCircleOutlined, EyeOutlined,
  SearchOutlined, AppstoreOutlined, UnorderedListOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { useEngineStore } from '@/store/useEngineStore';
import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';
import type { Capability, CapabilitySource } from '@/types';
import { AgentAvatar } from '@/components/agents/AgentAvatar';
import { AgentDetailDrawer } from '@/components/agents/AgentDetailDrawer';
import { AgentFormDrawer } from '@/components/agents/AgentFormDrawer';
import { SKILL_COLORS, STATUS_CONFIG, agentColor } from '@/components/agents/agentConstants';
import { useI18n } from '@/i18n';

export default function AgentsPage() {
  const { t } = useI18n();
  const engineMode = useEngineStore(s => s.mode);
  const engine = useEngineStore().getEngine();
  const runtimeMode = useAgentRuntimeStore(s => s.runtimeMode);
  const runtimeSkills = useAgentRuntimeStore(s => s.skills);
  const fetchRuntime = useAgentRuntimeStore(s => s.fetchRuntime);
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

  useEffect(() => {
    if (engineMode === 'real') {
      fetchRuntime();
    }
  }, [engineMode, fetchRuntime]);

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
    message.info(t('pages.agents.messages.batchDrained', { count: selectedRowKeys.length }));
  };
  const handleBatchStop = () => {
    selectedRowKeys.forEach(id => engine.unregisterAgent(id));
    refresh();
    setSelectedRowKeys([]);
    message.info(t('pages.agents.messages.batchStopped', { count: selectedRowKeys.length }));
  };
  const handleDelete = (id: string) => {
    engine.unregisterAgent(id);
    refresh();
    message.info(t('pages.agents.messages.deleted', { id }));
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
        message.success(t('pages.agents.messages.updated', { id: capData.agent_id }));
      } else {
        engine.registerAgent(capData);
        message.success(t('pages.agents.messages.registered', { id: capData.agent_id }));
      }
      refresh();
      setFormOpen(false);
      form.resetFields();
      setEditingAgent(null);
    }).catch(() => { });
  }, [engine, refresh, form, editingAgent, message]);

  // ========== 表格列 ==========
  const columns: ColumnsType<Capability> = [
    { title: t('pages.agents.columns.agentId'), dataIndex: 'agent_id', key: 'agent_id', width: 160, ellipsis: true,
      sorter: (a, b) => a.agent_id.localeCompare(b.agent_id),
    },
    {
      title: t('pages.agents.columns.displayName'), key: 'display_name', width: 160,
      render: (_: unknown, r: Capability) => (
        <Space>
          <AgentAvatar name={r.display_name} size={28} color={agentColor(r)} />
          <span>{r.display_name}</span>
        </Space>
      ),
    },
    {
      title: t('pages.agents.columns.skills'), dataIndex: 'skills', key: 'skills', width: 200,
      render: (skills: string[]) => (
        <Space size={4} wrap>
          {skills.map(s => <Tag key={s} color={SKILL_COLORS[s] || 'default'}>{s}</Tag>)}
        </Space>
      ),
    },
    {
      title: t('pages.agents.columns.status'), dataIndex: 'state', key: 'state', width: 100,
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
      title: t('pages.agents.columns.load'), dataIndex: 'load', key: 'load', width: 140,
      sorter: (a, b) => a.load - b.load,
      render: (load: number) => {
        const pct = Math.min(load * 20, 100);
        const color = pct > 80 ? '#ff4d4f' : pct > 50 ? '#fa8c16' : '#52c41a';
        return <Progress percent={pct} size="small" strokeColor={color} />;
      },
    },
    { title: t('pages.agents.columns.queue'), dataIndex: 'pending_tasks', key: 'pending_tasks', width: 70, sorter: (a, b) => a.pending_tasks - b.pending_tasks },
    { title: t('pages.agents.columns.weight'), dataIndex: 'weight', key: 'weight', width: 70, sorter: (a, b) => a.weight - b.weight },
    {
      title: t('pages.agents.columns.actions'), key: 'actions', width: 220, fixed: 'right',
      render: (_: unknown, r: Capability) => (
        <Space size="small">
          <Button size="small" icon={<EyeOutlined />} onClick={() => setDetailAgent(r)}>{t('pages.agents.actions.detail')}</Button>
          <Button size="small" icon={<PauseCircleOutlined />}
            onClick={() => { engine.drainAgent(r.agent_id); refresh(); }}
            disabled={r.state !== 'running'}>{t('pages.agents.actions.drain')}</Button>
          <Button size="small" danger icon={<StopOutlined />}
            onClick={() => { engine.unregisterAgent(r.agent_id); refresh(); }}>{t('pages.agents.actions.unregister')}</Button>
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
        <h3 style={{ margin: 0 }}>{t('pages.agents.title')}</h3>
        <Space>
          <Input
            placeholder={t('pages.agents.searchPlaceholder')}
            prefix={<SearchOutlined />}
            value={search}
            onChange={e => setSearch(e.target.value)}
            allowClear
            style={{ width: 200, maxWidth: 300 }}
          />
          <Radio.Group value={viewMode} onChange={e => setViewMode(e.target.value)} size="small">
            <Tooltip title={t('pages.agents.tableView')}><Radio.Button value="table"><UnorderedListOutlined /></Radio.Button></Tooltip>
            <Tooltip title={t('pages.agents.cardView')}><Radio.Button value="card"><AppstoreOutlined /></Radio.Button></Tooltip>
          </Radio.Group>
          {selectedRowKeys.length > 0 && (
            <Dropdown menu={{
              items: [
                { key: 'drain', icon: <PauseCircleOutlined />, label: t('pages.agents.batchDrain', { count: selectedRowKeys.length }), onClick: handleBatchDrain },
                { key: 'stop', icon: <StopOutlined />, label: t('pages.agents.batchStop', { count: selectedRowKeys.length }), onClick: handleBatchStop, danger: true },
              ],
            }}>
              <Button>{t('pages.agents.batchActions', { count: selectedRowKeys.length })}</Button>
            </Dropdown>
          )}
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateForm}>{t('pages.agents.create')}</Button>
        </Space>
      </div>

      {engineMode === 'real' && runtimeMode === 'agent' && runtimeSkills.length > 0 && (
        <Card
          title={t('pages.agents.hiveMindSkills')}
          size="small"
          style={{ marginBottom: 16 }}
          extra={<Tag color="purple">{t('pages.agents.agentMode')}</Tag>}
        >
          {runtimeSkills.map(s => (
            <Tag key={s} color={s.startsWith('mcp_') ? 'gold' : 'purple'} style={{ marginBottom: 4 }}>
              {s}
            </Tag>
          ))}
        </Card>
      )}

      {/* 空状态 */}
      {isEmpty && (
        <Card style={{ textAlign: 'center', padding: 48 }}>
          <Empty
            image={<AgentAvatar name="?" size={64} color="#d9d9d9" />}
            description={t('pages.agents.empty')}
          >
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateForm}>{t('pages.agents.registerFirst')}</Button>
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
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total) => t('pages.agents.totalCount', { count: total }) }}
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
                    <Tooltip title={t('pages.agents.card.detail')} key="detail"><EyeOutlined /></Tooltip>,
                    <Tooltip title={t('pages.agents.card.drain')} key="drain"><PauseCircleOutlined onClick={e => { e.stopPropagation(); engine.drainAgent(a.agent_id); refresh(); }} /></Tooltip>,
                    <Popconfirm title={t('pages.agents.confirmDelete')} onConfirm={e => { e?.stopPropagation(); handleDelete(a.agent_id); }} onCancel={e => e?.stopPropagation()} key="delete">
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

      <AgentFormDrawer
        open={formOpen}
        editingAgent={editingAgent}
        form={form}
        capSource={capSource}
        setCapSource={setCapSource}
        onClose={() => { setFormOpen(false); setEditingAgent(null); form.resetFields(); }}
        onSubmit={handleFormSubmit}
      />

      <AgentDetailDrawer
        agent={detailAgent}
        onClose={() => setDetailAgent(null)}
        onEdit={openEditForm}
        onDrain={(id) => { engine.drainAgent(id); refresh(); }}
      />

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