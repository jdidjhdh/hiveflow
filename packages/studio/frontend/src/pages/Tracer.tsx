import { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Input, List, Timeline, Tag, Empty, Card, Row, Col, Alert } from 'antd';
import { SearchOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, SyncOutlined } from '@ant-design/icons';
import { useEventStore } from '@/store/useEventStore';
import { useEngineStore } from '@/store/useEngineStore';
import { apiFetch, getErrorMessage } from '@/api';
import ApiErrorAlert from '@/components/ApiErrorAlert';
import { DemoDataBanner } from '@/components/RealModeRequired';
import { useI18n } from '@/i18n';
import type { EventRecord } from '@/types';

interface AuditEntry {
  agent: string;
  action: string;
  key: string;
  timestamp: number;
}

export default function TracerPage() {
  const { t } = useI18n();
  const events = useEventStore(s => s.events);
  const engineMode = useEngineStore(s => s.mode);
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [selectedTrace, setSelectedTrace] = useState<string | null>(searchParams.get('intent_id'));
  const [auditEvents, setAuditEvents] = useState<AuditEntry[]>([]);
  const [auditError, setAuditError] = useState<string | null>(null);

  const loadAudit = useCallback(() => {
    if (engineMode !== 'real') {
      setAuditEvents([]);
      setAuditError(null);
      return;
    }
    const intentId = selectedTrace || '';
    const url = intentId
      ? `/api/replay/audit?intent_id=${encodeURIComponent(intentId)}&limit=50`
      : '/api/replay/audit?limit=50';
    setAuditError(null);
    apiFetch(url)
      .then(data => setAuditEvents(data.events || data.entries || []))
      .catch((e) => {
        setAuditEvents([]);
        setAuditError(getErrorMessage(e));
      });
  }, [engineMode, selectedTrace]);

  useEffect(() => {
    loadAudit();
  }, [loadAudit]);

  const traceMap = new Map<string, EventRecord[]>();
  events.forEach(evt => {
    const traceId = evt.data?.intent_id || evt.data?.trace_id || evt.topic;
    if (!traceMap.has(traceId)) traceMap.set(traceId, []);
    traceMap.get(traceId)!.push(evt);
  });

  const filteredTraces = Array.from(traceMap.entries())
    .filter(([id]) => !search || id.toLowerCase().includes(search.toLowerCase()));

  const selectedEvents = selectedTrace ? (traceMap.get(selectedTrace) ?? []) : [];

  const topicIcon = (topic: string) => {
    if (topic.includes('completed')) return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
    if (topic.includes('failed')) return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
    if (topic.includes('running') || topic.includes('assigned')) return <SyncOutlined spin style={{ color: '#1890ff' }} />;
    return <ClockCircleOutlined style={{ color: '#faad14' }} />;
  };

  const statusLabel = (isCompleted: boolean, isFailed: boolean) => {
    if (isCompleted) return t('pages.tracer.status.completed');
    if (isFailed) return t('pages.tracer.status.failed');
    return t('pages.tracer.status.inProgress');
  };

  return (
    <>
      <DemoDataBanner message={t('pages.tracer.demoBanner')} />
      <ApiErrorAlert error={auditError} onRetry={loadAudit} />
      <Row gutter={[16, 16]} style={{ height: '100%' }}>
      <Col xs={24} sm={24} md={10} lg={8} xl={7}>
        <Card title={t('pages.tracer.intentList')} size="small" extra={
          <Input
            placeholder={t('pages.tracer.searchPlaceholder')}
            prefix={<SearchOutlined />}
            size="small"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: '100%' }}
          />
        }>
          {filteredTraces.length === 0 ? (
            <Empty description={t('pages.tracer.noTraceData')} />
          ) : (
            <List
              size="small"
              dataSource={filteredTraces}
              renderItem={([id, evts]) => {
                const lastEvt = evts[evts.length - 1];
                const isCompleted = lastEvt?.topic.includes('completed');
                const isFailed = lastEvt?.topic.includes('failed');
                return (
                  <List.Item
                    style={{
                      cursor: 'pointer',
                      background: selectedTrace === id ? '#f0f0ff' : undefined,
                      padding: '8px 12px',
                      borderRadius: 6,
                    }}
                    onClick={() => setSelectedTrace(id)}
                  >
                    <List.Item.Meta
                      avatar={topicIcon(lastEvt?.topic ?? '')}
                      title={<span style={{ fontSize: 12 }}>{id}</span>}
                      description={
                        <span style={{ fontSize: 11 }}>
                          <Tag color={isCompleted ? 'success' : isFailed ? 'error' : 'processing'}>
                            {statusLabel(!!isCompleted, !!isFailed)}
                          </Tag>
                          {new Date((lastEvt?.timestamp ?? 0) * 1000).toLocaleTimeString()}
                        </span>
                      }
                    />
                  </List.Item>
                );
              }}
            />
          )}
        </Card>
      </Col>

      <Col xs={24} sm={24} md={14} lg={16} xl={17}>
        {engineMode === 'real' && auditEvents.length > 0 && (
          <Alert
            type="success"
            showIcon
            style={{ marginBottom: 12 }}
            message={t('pages.tracer.auditLoaded', { count: auditEvents.length })}
          />
        )}
        <Card title={selectedTrace ? t('pages.tracer.traceDetail', { id: selectedTrace }) : t('pages.tracer.selectIntent')} size="small"
          extra={selectedTrace ? <Link to={`/replay?intent_id=${encodeURIComponent(selectedTrace)}`}>{t('pages.tracer.replayLink')}</Link> : null}
        >
          {!selectedTrace ? (
            <Empty description={t('pages.tracer.selectFromList')} />
          ) : (
            <>
              <Timeline
                items={selectedEvents.map((evt, i) => ({
                  key: i,
                  color: evt.topic.includes('completed') ? 'green'
                    : evt.topic.includes('failed') ? 'red'
                    : evt.topic.includes('running') ? 'blue'
                    : 'gray',
                  dot: topicIcon(evt.topic),
                  children: (
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{evt.topic}</div>
                      <div style={{ fontSize: 11, color: '#888' }}>
                        {new Date(evt.timestamp * 1000).toLocaleTimeString()}
                      </div>
                      <pre style={{ fontSize: 11, maxHeight: 100, overflow: 'auto', background: '#fafafa', padding: 4, borderRadius: 4 }}>
                        {JSON.stringify(evt.data?.payload ?? evt.data, null, 2).slice(0, 300)}
                      </pre>
                    </div>
                  ),
                }))}
              />
              {engineMode === 'real' && auditEvents.length > 0 && (
                <Card title={t('pages.tracer.auditTimeline')} size="small" style={{ marginTop: 16 }}>
                  <Timeline
                    items={auditEvents.map((e, i) => ({
                      key: `audit-${i}`,
                      children: (
                        <div style={{ fontSize: 12 }}>
                          <Tag>{e.action}</Tag> {e.agent} → {e.key}
                          <div style={{ color: '#888', fontSize: 11 }}>
                            {new Date(e.timestamp * 1000).toLocaleTimeString()}
                          </div>
                        </div>
                      ),
                    }))}
                  />
                </Card>
              )}
            </>
          )}
        </Card>
      </Col>
    </Row>
    </>
  );
}
