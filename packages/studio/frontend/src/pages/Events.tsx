import { useEffect, useMemo } from 'react';
import { Card, Button, Space, Input, Select, Tag } from 'antd';
import { PauseCircleOutlined, CaretRightOutlined, ClearOutlined, FilterOutlined } from '@ant-design/icons';
import { useEventStore } from '@/store/useEventStore';
import { useEngineStore } from '@/store/useEngineStore';
import { getWsManager } from '@/engine/ws/WsConnectionManager';
import { useI18n } from '@/i18n';

export default function EventsPage() {
  const { t } = useI18n();
  const { events, paused, setPaused, clear, filters, setFilters, addEvent } = useEventStore();
  const engineMode = useEngineStore(s => s.mode);

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
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Button
            icon={paused ? <CaretRightOutlined /> : <PauseCircleOutlined />}
            onClick={() => setPaused(!paused)}
            type={paused ? 'primary' : 'default'}
          >
            {paused ? t('pages.events.resume') : t('pages.events.pause')}
          </Button>
          <Button icon={<ClearOutlined />} onClick={clear}>{t('pages.events.clear')}</Button>
        </Space>
        <Space>
          <FilterOutlined />
          <Select
            allowClear
            placeholder={t('pages.events.filterByTopic')}
            style={{ width: 200 }}
            value={filters.topic || undefined}
            onChange={(v) => setFilters({ topic: v })}
            options={topicOptions}
          />
          <Input
            placeholder={t('pages.events.filterByAgent')}
            style={{ width: 200 }}
            value={filters.agent || ''}
            onChange={e => setFilters({ agent: e.target.value || undefined })}
          />
          <Tag>{t('pages.events.count', { filtered: filteredEvents.length, total: events.length })}</Tag>
          {engineMode === 'real' && <Tag color="green">{t('pages.events.liveMode')}</Tag>}
        </Space>
      </div>

      <Card style={{ flex: 1, overflow: 'hidden' }} styles={{ body: { padding: 0, height: '100%' } }}>
        <div className="event-console" style={{ height: '100%' }}>
          {filteredEvents.length === 0 && (
            <div style={{ color: '#888', padding: 20 }}>
              {paused ? t('pages.events.paused') : t('pages.events.noEvents')}
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
