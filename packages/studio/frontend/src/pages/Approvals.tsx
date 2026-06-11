import { useCallback, useEffect, useState } from 'react';
import { Button, Card, List, Space, Tag, Typography, message, Input, Alert } from 'antd';
import { CheckOutlined, CloseOutlined, ReloadOutlined } from '@ant-design/icons';
import { apiFetch } from '@/utils/api';
import { useEngineStore } from '@/store/useEngineStore';
import { useEventStore } from '@/store/useEventStore';
import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';

interface HITLGate {
  gate_id: string;
  workflow_id: string;
  node_id: string;
  action: string;
  prompt: string;
  status: string;
  context?: Record<string, unknown>;
  human_comment?: string;
}

function isPlanGate(gate: HITLGate): boolean {
  return gate.node_id === 'plan_approval';
}

function getPlanFromContext(context?: Record<string, unknown>): unknown {
  return context?.plan;
}

function validatePlanJson(parsed: unknown): string | null {
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return '计划必须是 JSON 对象';
  }
  if (!('final_answer' in (parsed as Record<string, unknown>))) {
    return '计划必须包含 final_answer 节点';
  }
  return null;
}

export default function ApprovalsPage() {
  const { mode } = useEngineStore();
  const events = useEventStore(s => s.events);
  const runtimeMode = useAgentRuntimeStore(s => s.runtimeMode);
  const [gates, setGates] = useState<HITLGate[]>([]);
  const [loading, setLoading] = useState(false);
  const [comments, setComments] = useState<Record<string, string>>({});
  const [planEdits, setPlanEdits] = useState<Record<string, string>>({});

  const loadPending = useCallback(async () => {
    if (mode !== 'real') {
      setGates([]);
      return;
    }
    setLoading(true);
    try {
      const data = await apiFetch('/api/hitl/pending');
      const list: HITLGate[] = data.gates || [];
      setGates(list);
      setPlanEdits(prev => {
        const next = { ...prev };
        for (const gate of list) {
          if (isPlanGate(gate) && next[gate.gate_id] === undefined) {
            next[gate.gate_id] = JSON.stringify(getPlanFromContext(gate.context), null, 2);
          }
        }
        return next;
      });
    } catch (e) {
      message.error(String(e));
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    loadPending();
    const timer = setInterval(loadPending, 5000);
    return () => clearInterval(timer);
  }, [loadPending]);

  useEffect(() => {
    const last = events[events.length - 1];
    if (last?.topic === 'hitl.pending') {
      loadPending();
    }
  }, [events, loadPending]);

  const respond = async (gateId: string, approved: boolean, modifiedData?: unknown) => {
    try {
      const body: Record<string, unknown> = {
        approved,
        comment: comments[gateId] || '',
      };
      if (modifiedData !== undefined) {
        body.modified_data = modifiedData;
      }
      await apiFetch(`/api/hitl/${gateId}/respond`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      message.success(approved ? '已批准' : '已拒绝');
      await loadPending();
    } catch (e) {
      message.error(String(e));
    }
  };

  const approvePlan = async (gate: HITLGate) => {
    const raw = planEdits[gate.gate_id] ?? '';
    const original = JSON.stringify(getPlanFromContext(gate.context));
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      message.error('计划 JSON 格式无效');
      return;
    }
    const err = validatePlanJson(parsed);
    if (err) {
      message.error(err);
      return;
    }
    const normalized = JSON.stringify(parsed);
    if (normalized !== original) {
      await respond(gate.gate_id, true, { plan: parsed });
    } else {
      await respond(gate.gate_id, true);
    }
  };

  if (mode !== 'real') {
    return (
      <Card>
        <Typography.Paragraph>
          人工审批需要在<strong>真实模式</strong>下使用。请打开顶部开关连接后端引擎，并在工作流中加入「人工审批」节点。
        </Typography.Paragraph>
      </Card>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>待审批任务</h3>
        <Button icon={<ReloadOutlined />} onClick={loadPending} loading={loading}>
          刷新
        </Button>
      </div>

      {runtimeMode !== 'agent' && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="Agent 计划审批需开启 Agent 模式，并设置环境变量 HIVEFLOW_PLAN_HITL=true"
        />
      )}

      <List
        loading={loading}
        dataSource={gates}
        locale={{ emptyText: '暂无待审批项' }}
        renderItem={(gate) => (
          <List.Item
            key={gate.gate_id}
            actions={[
              <Button
                key="approve"
                type="primary"
                icon={<CheckOutlined />}
                onClick={() => (isPlanGate(gate) ? approvePlan(gate) : respond(gate.gate_id, true))}
              >
                批准
              </Button>,
              <Button
                key="reject"
                danger
                icon={<CloseOutlined />}
                onClick={() => respond(gate.gate_id, false)}
              >
                拒绝
              </Button>,
            ]}
          >
            <List.Item.Meta
              title={
                <Space>
                  <span>{gate.prompt}</span>
                  <Tag>{gate.action}</Tag>
                  {isPlanGate(gate) && <Tag color="purple">执行计划</Tag>}
                </Space>
              }
              description={
                <>
                  <div>工作流: {gate.workflow_id} · 节点: {gate.node_id}</div>
                  {isPlanGate(gate) && (
                    <Input.TextArea
                      rows={12}
                      value={planEdits[gate.gate_id] || ''}
                      onChange={(e) => setPlanEdits(c => ({ ...c, [gate.gate_id]: e.target.value }))}
                      style={{ marginTop: 8, fontFamily: 'monospace', fontSize: 12 }}
                      placeholder="执行计划 JSON（需含 final_answer 节点）"
                    />
                  )}
                  <Input.TextArea
                    rows={2}
                    placeholder="审批意见（可选）"
                    value={comments[gate.gate_id] || ''}
                    onChange={(e) => setComments((c) => ({ ...c, [gate.gate_id]: e.target.value }))}
                    style={{ marginTop: 8 }}
                  />
                </>
              }
            />
          </List.Item>
        )}
      />
    </div>
  );
}
