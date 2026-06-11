import { useEffect, useMemo } from 'react';
import { Card, Button, Space, Input, Select, Tag } from 'antd';
import { PauseCircleOutlined, CaretRightOutlined, ClearOutlined, FilterOutlined } from '@ant-design/icons';
import { useEventStore } from '@/store/useEventStore';
import { useEngineStore } from '@/store/useEngineStore';
import { getWsManager } from '@/engine/ws/WsConnectionManager';

export default function EventsPage() {
  const { events, paused, setPaused, clear, filters, setFilters, addEvent } = useEventStore();
  const engineMode = useEngineStore(s => s.mode);

  // 真实模式下订阅 WebSocket 事件
  useEffect(() => {
    if (engineMode === 'real') {
      const wsManager = getWsManager();
      const cleanup = wsManager.onEvent((topic, data) => {
        if (!paused) {
          addEvent(topic, data);
        }
      });
      return cleanup;
    }
  }, [engineMode, paused, addEvent]);

  const filteredEvents = useMemo(() => {
    return events.filter(evt => {
      if (filters.topic && !evt.topic.includes(filters.topic)) return false;
      if (filters.agent && evt.data?.emitter !== filters.agent) return false;
      return true;
    });
  }, [events, filters]);

  const topicOptions = useMemo(() => {
    const topics = new Set(events.map(e => e.topic));
    return Array.from(topics).map(t => ({ value: t, label: t }));
  }, [events]);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 工具栏 */}
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Button
            icon={paused ? <CaretRightOutlined /> : <PauseCircleOutlined />}
            onClick={() => setPaused(!paused)}
            type={paused ? 'primary' : 'default'}
          >
            {paused ? '继续' : '暂停'}
          </Button>
          <Button icon={<ClearOutlined />} onClick={clear}>清空</Button>
        </Space>
        <Space>
          <FilterOutlined />
          <Select
            allowClear
            placeholder="按主题过滤"
            style={{ width: 200 }}
            value={filters.topic || undefined}
            onChange={(v) => setFilters({ topic: v })}
            options={topicOptions}
          />
          <Input
            placeholder="按 Agent ID 过滤"
            style={{ width: 200 }}
            value={filters.agent || ''}
            onChange={e => setFilters({ agent: e.target.value || undefined })}
          />
          <Tag>{filteredEvents.length} / {events.length} 条</Tag>
          {engineMode === 'real' && <Tag color="green">实时模式</Tag>}
        </Space>
      </div>

      {/* 事件列表 */}
      <Card style={{ flex: 1, overflow: 'hidden' }} styles={{ body: { padding: 0, height: '100%' } }}>
        <div className="event-console" style={{ height: '100%' }}>
          {filteredEvents.length === 0 && (
            <div style={{ color: '#888', padding: 20 }}>
              {paused ? '已暂停' : '暂无事件，执行工作流后将在此显示...'}
            </div>
          )}
          {filteredEvents.map((evt, i) => (
            <div key={i} className="event-line">
              <span className="event-time">
                [{new Date(evt.timestamp * 1000).toLocaleTimeString()}.{String(Math.floor((evt.timestamp % 1) * 1000)).padStart(3, '0')}]
              </span>{' '}
              <span className="event-topic">{evt.topic}</span>{' '}
              <Tag color="default" style={{ fontSize: 10 }}>{evt.data?.emitter || '-'}</Tag>{' '}
              <span style={{ color: '#ce9178' }}>
                {JSON.stringify(evt.data?.payload ?? evt.data, null, 0).slice(0, 200)}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}