import {
  Drawer, Button, Space, Tag, Card, Row, Col, Progress, Tooltip, Table,
} from 'antd';
import {
  PauseCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
} from '@ant-design/icons';
import type { Capability } from '@/types';
import { AgentAvatar } from './AgentAvatar';
import { STATUS_CONFIG, SKILL_COLORS, agentColor } from './agentConstants';

interface AgentDetailDrawerProps {
  agent: Capability | null;
  onClose: () => void;
  onEdit: (agent: Capability) => void;
  onDrain: (agentId: string) => void;
}

export function AgentDetailDrawer({ agent, onClose, onEdit, onDrain }: AgentDetailDrawerProps) {
  const cfg = agent ? STATUS_CONFIG[agent.state] : null;
  const loadPct = agent ? Math.min(agent.load * 20, 100) : 0;
  const loadColor = loadPct > 80 ? '#ff4d4f' : loadPct > 50 ? '#fa8c16' : '#52c41a';

  return (
    <Drawer
      title={
        agent ? (
          <Space>
            <AgentAvatar name={agent.display_name || '?'} size={32} color={agentColor(agent)} />
            <span>{agent.display_name}</span>
          </Space>
        ) : null
      }
      open={!!agent}
      onClose={onClose}
      width={500}
      extra={agent && (
        <Space>
          <Button size="small" onClick={() => { onEdit(agent); onClose(); }}>编辑</Button>
          <Button
            size="small"
            icon={<PauseCircleOutlined />}
            onClick={() => { onDrain(agent.agent_id); onClose(); }}
            disabled={agent.state !== 'running'}
          >
            排水
          </Button>
        </Space>
      )}
    >
      {agent && cfg && (
        <div>
          <Card size="small" style={{ marginBottom: 16 }}>
            <Row gutter={[16, 12]}>
              <Col span={12}>
                <div style={{ color: '#888', fontSize: 12 }}>Agent ID</div>
                <div style={{ fontWeight: 500 }}>{agent.agent_id}</div>
              </Col>
              <Col span={12}>
                <div style={{ color: '#888', fontSize: 12 }}>状态</div>
                <Space size={4}>
                  <span style={{
                    display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: cfg.color,
                    animation: agent.state === 'running' ? 'pulse 1.5s infinite' : undefined,
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
                <div style={{ fontWeight: 500 }}>{agent.pending_tasks}</div>
              </Col>
              <Col span={12}>
                <div style={{ color: '#888', fontSize: 12 }}>权重</div>
                <div style={{ fontWeight: 500 }}>{agent.weight}</div>
              </Col>
              <Col span={12}>
                <div style={{ color: '#888', fontSize: 12 }}>最后心跳</div>
                <div style={{ fontWeight: 500, fontSize: 12 }}>
                  {new Date(agent.last_heartbeat * 1000).toLocaleString()}
                </div>
              </Col>
            </Row>
          </Card>

          <div style={{ marginBottom: 16 }}>
            <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>技能标签</div>
            <Space size={4} wrap>
              {agent.skills.map(s => <Tag key={s} color={SKILL_COLORS[s] || 'default'}>{s}</Tag>)}
            </Space>
          </div>

          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={12}>
              <div style={{ color: '#888', fontSize: 12 }}>可读黑板键</div>
              <div>{agent.read_keys.length > 0 ? agent.read_keys.join(', ') : <span style={{ color: '#ccc' }}>无限制</span>}</div>
            </Col>
            <Col span={12}>
              <div style={{ color: '#888', fontSize: 12 }}>可写黑板键</div>
              <div>{agent.write_keys.length > 0 ? agent.write_keys.join(', ') : <span style={{ color: '#ccc' }}>无限制</span>}</div>
            </Col>
          </Row>

          {agent.task_handler && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: '#888', fontSize: 12 }}>任务处理器</div>
              <Tag color="blue">{agent.task_handler}</Tag>
            </div>
          )}

          {agent.description && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: '#888', fontSize: 12 }}>描述</div>
              <div>{agent.description}</div>
            </div>
          )}

          {agent.model_config && (
            <Card title="AI 模型配置" size="small" style={{ marginBottom: 16 }}>
              <Row gutter={[16, 8]}>
                <Col span={12}><span style={{ color: '#888' }}>提供商: </span>{agent.model_config.provider}</Col>
                <Col span={12}><span style={{ color: '#888' }}>模型: </span>{agent.model_config.model_name}</Col>
                {agent.model_config.system_prompt && (
                  <Col span={24}><span style={{ color: '#888' }}>提示词: </span><span style={{ fontSize: 12 }}>{agent.model_config.system_prompt}</span></Col>
                )}
                {agent.model_config.tools && agent.model_config.tools.length > 0 && (
                  <Col span={24}><span style={{ color: '#888' }}>工具: </span><Space size={4}>{agent.model_config.tools.map(t => <Tag key={t}>{t}</Tag>)}</Space></Col>
                )}
              </Row>
            </Card>
          )}

          <Card title="负载历史 (最近 1 小时)" size="small" style={{ marginBottom: 16 }}>
            {agent.load_history.length > 0 ? (
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 60, paddingTop: 8 }}>
                {agent.load_history.map((p, i) => (
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

          <Card title="最近任务" size="small">
            {agent.recent_tasks.length > 0 ? (
              <Table
                dataSource={agent.recent_tasks.slice().reverse().map((t, i) => ({ ...t, key: i }))}
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
      )}
    </Drawer>
  );
}
