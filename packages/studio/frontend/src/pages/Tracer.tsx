import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Input, List, Timeline, Tag, Empty, Card, Row, Col, Alert } from 'antd';
import { SearchOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, SyncOutlined } from '@ant-design/icons';
import { useEventStore } from '@/store/useEventStore';
import { useEngineStore } from '@/store/useEngineStore';
import { apiFetch } from '@/utils/api';
import type { EventRecord } from '@/types';

interface AuditEntry {
  agent: string;
  action: string;
  key: string;
  timestamp: number;
}

export default function TracerPage() {
  const events = useEventStore(s => s.events);
  const engineMode = useEngineStore(s => s.mode);
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [selectedTrace, setSelectedTrace] = useState<string | null>(searchParams.get('intent_id'));
  const [auditEvents, setAuditEvents] = useState<AuditEntry[]>([]);

  useEffect(() => {
    if (engineMode !== 'real') {
      setAuditEvents([]);
      return;
    }
    const intentId = selectedTrace || '';
    const url = intentId
      ? `/api/replay/audit?intent_id=${encodeURIComponent(intentId)}&limit=50`
      : '/api/replay/audit?limit=50';
    apiFetch(url)
      .then(data => setAuditEvents(data.events || data.entries || []))
      .catch(() => setAuditEvents([]));
  }, [engineMode, selectedTrace]);

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

  return (
    <Row gutter={[16, 16]} style={{ height: '100%' }}>
      <Col xs={24} sm={24} md={10} lg={8} xl={7}>
        <Card title="意图列表" size="small" extra={
          <Input
            placeholder="搜索 intent_id / trace_id"
            prefix={<SearchOutlined />}
            size="small"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: '100%' }}
          />
        }>
          {filteredTraces.length === 0 ? (
            <Empty description="暂无追踪数据" />
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
                            {isCompleted ? '完成' : isFailed ? '失败' : '进行中'}
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
            message={`已加载 ${auditEvents.length} 条真实 audit 记录`}
          />
        )}
        <Card title={selectedTrace ? `追踪详情: ${selectedTrace}` : '选择一个意图查看详情'} size="small"
          extra={selectedTrace ? <Link to={`/replay?intent_id=${encodeURIComponent(selectedTrace)}`}>Replay 回放</Link> : null}
        >
          {!selectedTrace ? (
            <Empty description="请从左侧列表选择意图" />
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
                <Card title="Audit 时间线 (Replay)" size="small" style={{ marginTop: 16 }}>
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
  );
}
