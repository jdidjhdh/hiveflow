import { useCallback, useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  Card, Input, Button, Timeline, Tag, Empty, Row, Col, Typography, Space, Alert,
} from 'antd';
import { SearchOutlined, ReloadOutlined, HistoryOutlined } from '@ant-design/icons';
import { apiFetch } from '@/api';
import { useEngineStore } from '@/store/useEngineStore';
import { useI18n } from '@/i18n';

interface AuditEntry {
  agent?: string;
  action?: string;
  key?: string;
  timestamp?: number;
}

interface CheckpointEntry {
  checkpoint_id?: string;
  node_id?: string;
  timestamp?: number;
}

export default function ReplayPage() {
  const { t } = useI18n();
  const engineMode = useEngineStore(s => s.mode);
  const [searchParams, setSearchParams] = useSearchParams();
  const [intentId, setIntentId] = useState(searchParams.get('intent_id') || '');
  const [workflowId, setWorkflowId] = useState('');
  const [auditEvents, setAuditEvents] = useState<AuditEntry[]>([]);
  const [checkpoints, setCheckpoints] = useState<CheckpointEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionInfo, setSessionInfo] = useState<Record<string, unknown> | null>(null);

  const loadReplay = useCallback(async () => {
    if (engineMode !== 'real') {
      setAuditEvents([]);
      setCheckpoints([]);
      setSessionInfo(null);
      return;
    }
    setLoading(true);
    try {
      if (intentId.trim()) {
        const data = await apiFetch(
          `/api/replay/audit?intent_id=${encodeURIComponent(intentId.trim())}&limit=100`
        );
        setSessionInfo(data);
        setAuditEvents(data.events || data.entries || []);
      } else {
        const data = await apiFetch('/api/replay/audit?limit=100');
        setSessionInfo(null);
        setAuditEvents(data.events || []);
      }
      if (workflowId.trim()) {
        const cp = await apiFetch(
          `/api/replay/checkpoints/${encodeURIComponent(workflowId.trim())}`
        );
        setCheckpoints(cp.checkpoints || []);
      } else {
        setCheckpoints([]);
      }
    } catch {
      setAuditEvents([]);
      setCheckpoints([]);
    } finally {
      setLoading(false);
    }
  }, [engineMode, intentId, workflowId]);

  useEffect(() => {
    loadReplay();
  }, [loadReplay]);

  const applyIntentSearch = () => {
    if (intentId.trim()) {
      setSearchParams({ intent_id: intentId.trim() });
    } else {
      setSearchParams({});
    }
    loadReplay();
  };

  if (engineMode !== 'real') {
    return (
      <Card>
        <Typography.Paragraph>
          {t('pages.replay.realModeRequired')}
        </Typography.Paragraph>
      </Card>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>
          <HistoryOutlined style={{ marginRight: 8 }} />
          {t('pages.replay.title')}
        </h3>
        <Button icon={<ReloadOutlined />} onClick={loadReplay} loading={loading}>
          {t('pages.replay.refresh')}
        </Button>
      </div>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message={t('pages.replay.infoAlert')}
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title={t('pages.replay.intentReplay')} size="small">
            <Space.Compact style={{ width: '100%', marginBottom: 12 }}>
              <Input
                placeholder={t('pages.replay.intentIdPlaceholder')}
                prefix={<SearchOutlined />}
                value={intentId}
                onChange={(e) => setIntentId(e.target.value)}
                onPressEnter={applyIntentSearch}
              />
              <Button type="primary" onClick={applyIntentSearch}>{t('pages.replay.query')}</Button>
            </Space.Compact>
            {sessionInfo && (
              <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                {t('pages.replay.sessionInfo', {
                  intentId: String(sessionInfo.intent_id || intentId),
                  count: auditEvents.length,
                })}
              </Typography.Text>
            )}
            {auditEvents.length === 0 ? (
              <Empty description={t('pages.replay.noAuditRecords')} />
            ) : (
              <Timeline
                items={auditEvents.map((evt, i) => ({
                  key: i,
                  children: (
                    <div>
                      <Tag>{evt.action || 'event'}</Tag>
                      <strong>{evt.agent || 'unknown'}</strong>
                      <div style={{ fontSize: 12, color: '#666' }}>{evt.key}</div>
                      <div style={{ fontSize: 11, color: '#999' }}>
                        {evt.timestamp ? new Date(evt.timestamp * 1000).toLocaleString() : ''}
                      </div>
                    </div>
                  ),
                }))}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title={t('pages.replay.checkpointTimeline')} size="small">
            <Space.Compact style={{ width: '100%', marginBottom: 12 }}>
              <Input
                placeholder={t('pages.replay.workflowIdPlaceholder')}
                value={workflowId}
                onChange={(e) => setWorkflowId(e.target.value)}
                onPressEnter={loadReplay}
              />
              <Button onClick={loadReplay}>{t('pages.replay.load')}</Button>
            </Space.Compact>
            {checkpoints.length === 0 ? (
              <Empty description={t('pages.replay.noCheckpointHint')} />
            ) : (
              <Timeline
                items={checkpoints.map((cp, i) => ({
                  key: i,
                  children: (
                    <div>
                      <Tag color="blue">{cp.node_id || 'node'}</Tag>
                      <span>{cp.checkpoint_id}</span>
                      <div style={{ fontSize: 11, color: '#999' }}>
                        {cp.timestamp ? new Date(cp.timestamp * 1000).toLocaleString() : ''}
                      </div>
                    </div>
                  ),
                }))}
              />
            )}
          </Card>
        </Col>
      </Row>

      <div style={{ marginTop: 16 }}>
        <Link to="/tracer">{t('pages.replay.goToTracer')}</Link>
      </div>
    </div>
  );
}
