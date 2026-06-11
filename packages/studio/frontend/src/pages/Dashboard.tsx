import { useEffect, useRef, useState, useCallback } from 'react';
import { Row, Col, Card, Statistic, Spin, Empty } from 'antd';
import { CheckCircleOutlined, ThunderboltOutlined, TeamOutlined, ClockCircleOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { useEngineStore } from '@/store/useEngineStore';
import { useEventStore } from '@/store/useEventStore';
import { getWsManager } from '@/engine/ws/WsConnectionManager';
import { apiFetch } from '@/utils/api';
import type { MetricsSnapshot } from '@/types';

const MOCK_METRICS: MetricsSnapshot = {
  counters: { total_intents: 0, completed_intents: 0, failed_intents: 0, timed_out_intents: 0 },
  gauges: { active_agents: 0, total_load: 0 },
};

function normalizeMetrics(raw: Record<string, unknown>): MetricsSnapshot {
  const counters = (raw.counters as Record<string, number>) || {};
  return {
    counters: {
      total_intents: counters.total_intents ?? counters.intents_total ?? 0,
      completed_intents: counters.completed_intents ?? counters.workflows_completed ?? 0,
      failed_intents: counters.failed_intents ?? counters.workflows_failed ?? 0,
      timed_out_intents: counters.timed_out_intents ?? 0,
    },
    gauges: {
      active_agents: Number(raw.active_agents ?? counters.active_agents ?? 0),
      total_load: Number(raw.total_load ?? counters.total_load ?? 0),
    },
  };
}

export default function DashboardPage() {
  const engineMode = useEngineStore(s => s.mode);
  const engine = useEngineStore().getEngine();
  const events = useEventStore(s => s.events);
  const [metrics, setMetrics] = useState<MetricsSnapshot>(() =>
    engineMode === 'mock' ? engine.getMetrics() : MOCK_METRICS
  );
  const [loading, setLoading] = useState(engineMode === 'real');
  const lastWsMetricsRef = useRef(0);

  const fetchRestMetrics = useCallback(async () => {
    try {
      const raw = await apiFetch('/api/metrics');
      setMetrics(normalizeMetrics(raw));
      setLoading(false);
    } catch {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (engineMode === 'mock') {
      setLoading(false);
      const timer = setInterval(() => {
        setMetrics(engine.getMetrics());
      }, 2000);
      return () => clearInterval(timer);
    }

    fetchRestMetrics();
    const wsManager = getWsManager();
    const cleanupMetrics = wsManager.onMetrics((newMetrics) => {
      setMetrics(normalizeMetrics(newMetrics as unknown as Record<string, unknown>));
      lastWsMetricsRef.current = Date.now();
      setLoading(false);
    });
    wsManager.requestEngineInfo();

    const pollTimer = setInterval(() => {
      const stale = Date.now() - lastWsMetricsRef.current > 30000;
      if (stale || !wsManager.isConnected()) {
        fetchRestMetrics();
      }
    }, 5000);

    return () => {
      cleanupMetrics();
      clearInterval(pollTimer);
    };
  }, [engine, engineMode, fetchRestMetrics]);

  const m = metrics;
  const agents = engine.getAgents();
  const recentEvents = events.slice(-20);

  return (
    <Spin spinning={loading}>
      <div>
        {loading && <div style={{ textAlign: 'center', padding: 8, color: '#888', fontSize: 13 }}>正在连接引擎...</div>}
        {!loading && (
        <div>
        <h3 style={{ marginBottom: 16 }}>实时仪表盘 {engineMode === 'real' && <span style={{ fontSize: 12, color: '#52c41a' }}>(实时模式)</span>}</h3>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={12} md={6}>
          <Card className="stat-card">
            <Statistic title="总意图数" value={m.counters?.total_intents ?? 0} prefix={<ThunderboltOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card className="stat-card">
            <Statistic
              title="成功率"
              value={(m.counters?.total_intents ?? 0) > 0
                ? Math.round(((m.counters?.completed_intents ?? 0) / (m.counters?.total_intents ?? 1)) * 100)
                : 100}
              suffix="%"
              valueStyle={{ color: (m.counters?.total_intents ?? 0) > 0 && ((m.counters?.completed_intents ?? 0) / (m.counters?.total_intents ?? 1)) < 0.8 ? '#ff4d4f' : '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card className="stat-card">
            <Statistic title="活跃 Agent" value={m.gauges?.active_agents ?? 0} prefix={<TeamOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card className="stat-card">
            <Statistic title="总负载" value={m.gauges?.total_load ?? 0} prefix={<ClockCircleOutlined />} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card title="Agent 负载分布">
            {agents.length === 0 ? (
              <Empty description="暂无 Agent 数据" style={{ padding: '40px 0' }} />
            ) : (
              <ReactECharts
                option={{
                  tooltip: { trigger: 'axis' },
                  grid: { left: 40, right: 20, top: 30, bottom: 40 },
                  xAxis: {
                    type: 'category',
                    data: agents.map(a => a.agent_id),
                    axisLabel: { rotate: 30, interval: 0 },
                  },
                  yAxis: { type: 'value', name: '负载' },
                  series: [{
                    type: 'bar',
                    data: agents.map(a => a.load),
                    itemStyle: { color: '#6366f1' },
                  }],
                }}
                style={{ height: 300 }}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="事件趋势">
            <ReactECharts
              option={{
                tooltip: { trigger: 'axis' },
                grid: { left: 40, right: 20, top: 30, bottom: 40 },
                xAxis: {
                  type: 'category',
                  data: recentEvents.slice(-10).map((_, i) => `E-${i + 1}`),
                },
                yAxis: { type: 'value', name: '事件数' },
                series: [{
                  type: 'line',
                  data: recentEvents.slice(-10).map(() => 1),
                  smooth: true,
                  itemStyle: { color: '#52c41a' },
                  areaStyle: { color: 'rgba(82, 196, 26, 0.1)' },
                }],
              }}
              style={{ height: 300 }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="实时事件流" size="small">
        {recentEvents.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#8c8c8c' }}>
            暂无事件，执行工作流后将在此显示...
          </div>
        ) : (
          <div className="event-console" style={{ maxHeight: 250, overflow: 'auto' }}>
            {recentEvents.map((evt, i) => (
              <div key={i} className="event-line">
                <span className="event-time">[{new Date(evt.timestamp * 1000).toLocaleTimeString()}]</span>{' '}
                <span className="event-topic">{evt.topic}</span>{' '}
                {JSON.stringify(evt.data?.payload ?? evt.data).slice(0, 120)}
              </div>
            ))}
          </div>
        )}
      </Card>
        </div>
        )}
      </div>
    </Spin>
  );
}
