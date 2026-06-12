import { useCallback, useEffect, useState } from 'react';
import { Button, Card, List, Space, Tag, Typography, message, Input, Alert } from 'antd';
import { CheckOutlined, CloseOutlined, ReloadOutlined } from '@ant-design/icons';
import { apiFetch } from '@/api';
import { useEngineStore } from '@/store/useEngineStore';
import { useEventStore } from '@/store/useEventStore';
import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';
import { useI18n } from '@/i18n';

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

export default function ApprovalsPage() {
  const { t } = useI18n();
  const { mode } = useEngineStore();
  const events = useEventStore(s => s.events);
  const runtimeMode = useAgentRuntimeStore(s => s.runtimeMode);
  const [gates, setGates] = useState<HITLGate[]>([]);
  const [loading, setLoading] = useState(false);
  const [comments, setComments] = useState<Record<string, string>>({});
  const [planEdits, setPlanEdits] = useState<Record<string, string>>({});

  const validatePlanJson = useCallback((parsed: unknown): string | null => {
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return t('pages.approvals.messages.planMustBeObject');
    }
    if (!('final_answer' in (parsed as Record<string, unknown>))) {
      return t('pages.approvals.messages.planMustHaveFinalAnswer');
    }
    return null;
  }, [t]);

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
      message.success(approved ? t('pages.approvals.messages.approved') : t('pages.approvals.messages.rejected'));
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
      message.error(t('pages.approvals.messages.invalidPlanJson'));
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
          {t('pages.approvals.realModeRequired')}
        </Typography.Paragraph>
      </Card>
    );
  }

  return (
    <div data-testid="approvals-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>{t('pages.approvals.title')}</h3>
        <Button icon={<ReloadOutlined />} onClick={loadPending} loading={loading}>
          {t('pages.approvals.refresh')}
        </Button>
      </div>

      {runtimeMode !== 'agent' && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={t('pages.approvals.agentModeHint')}
        />
      )}

      <List
        loading={loading}
        dataSource={gates}
        locale={{ emptyText: t('pages.approvals.empty') }}
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
                {t('pages.approvals.approve')}
              </Button>,
              <Button
                key="reject"
                danger
                icon={<CloseOutlined />}
                onClick={() => respond(gate.gate_id, false)}
              >
                {t('pages.approvals.reject')}
              </Button>,
            ]}
          >
            <List.Item.Meta
              title={
                <Space>
                  <span>{gate.prompt}</span>
                  <Tag>{gate.action}</Tag>
                  {isPlanGate(gate) && <Tag color="purple">{t('pages.approvals.planTag')}</Tag>}
                </Space>
              }
              description={
                <>
                  <div>{t('pages.approvals.workflowNode', { workflowId: gate.workflow_id, nodeId: gate.node_id })}</div>
                  {isPlanGate(gate) && (
                    <Input.TextArea
                      rows={12}
                      value={planEdits[gate.gate_id] || ''}
                      onChange={(e) => setPlanEdits(c => ({ ...c, [gate.gate_id]: e.target.value }))}
                      style={{ marginTop: 8, fontFamily: 'monospace', fontSize: 12 }}
                      placeholder={t('pages.approvals.planPlaceholder')}
                    />
                  )}
                  <Input.TextArea
                    rows={2}
                    placeholder={t('pages.approvals.commentPlaceholder')}
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
