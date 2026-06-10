import { useState } from 'react';
import { Input, List, Timeline, Tag, Empty, Card } from 'antd';
import { SearchOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, SyncOutlined } from '@ant-design/icons';
import { useEventStore } from '@/store/useEventStore';
import type { EventRecord } from '@/types';

export default function TracerPage() {
  const events = useEventStore(s => s.events);
  const [search, setSearch] = useState('');
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null);

  // 提取所有唯一的 trace_id，按意图分组
  const traceMap = new Map<string, EventRecord[]>();
  events.forEach(evt => {
    const traceId = evt.data?.trace_id || evt.topic;
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
    <div style={{ display: 'flex', height: '100%', gap: 16 }}>
      {/* 左侧意图列表 */}
      <div style={{ width: 320, flexShrink: 0 }}>
        <Card title="意图列表" size="small" extra={
          <Input
            placeholder="搜索 trace_id"
            prefix={<SearchOutlined />}
            size="small"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: 180 }}
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
      </div>

      {/* 右侧时间线 */}
      <div style={{ flex: 1 }}>
        <Card title={selectedTrace ? `追踪详情: ${selectedTrace}` : '选择一个意图查看详情'} size="small">
          {!selectedTrace ? (
            <Empty description="请从左侧列表选择意图" />
          ) : (
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
          )}
        </Card>
      </div>
    </div>
  );
}