import { useEffect, useState } from 'react';
import { Row, Col, Card, Statistic, Spin } from 'antd';
import { CheckCircleOutlined, ThunderboltOutlined, TeamOutlined, ClockCircleOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { useEngineStore } from '@/store/useEngineStore';
import { useEventStore } from '@/store/useEventStore';
import { getWsManager } from '@/engine/ws/WsConnectionManager';
import type { MetricsSnapshot } from '@/types';

const MOCK_METRICS: MetricsSnapshot = {
  counters: { total_intents: 0, completed_intents: 0, failed_intents: 0, timed_out_intents: 0 },
  gauges: { active_agents: 0, total_load: 0 },
  histograms: { e2e_latency: { p50: 0, p95: 0, p99: 0 } },
  agents: {},
};

export default function DashboardPage() {
  const engineMode = useEngineStore(s => s.mode);
  const engine = useEngineStore().getEngine();
  const events = useEventStore(s => s.events);
  const [metrics, setMetrics] = useState<MetricsSnapshot>(() =>
    engineMode === 'mock' ? engine.getMetrics() : MOCK_METRICS
  );
  const [loading, setLoading] = useState(engineMode === 'real');

  useEffect(() => {
    if (engineMode === 'mock') {
      setLoading(false);
      const timer = setInterval(() => {
        setMetrics(engine.getMetrics());
      }, 2000);
      return () => clearInterval(timer);
    } else {
      setLoading(true);
      // 真实模式：通过 WebSocket 接收指标
      const wsManager = getWsManager();
      const cleanup = wsManager.onMetrics((newMetrics) => {
        setMetrics(newMetrics);
        setLoading(false);
      });

      // 请求初始指标
      wsManager.requestEngineInfo();

      return cleanup;
    }
  }, [engine, engineMode]);

  const m = metrics;
  const agents = m.agents ? Object.values(m.agents) : [];

  // 事件流最近20条
  const recentEvents = events.slice(-20);

  return (
    <Spin spinning={loading} tip="正在连接引擎...">
      <div>
        <h3 style={{ marginBottom: 16 }}>实时仪表盘 {engineMode === 'real' && <span style={{ fontSize: 12, color: '#52c41a' }}>(实时模式)</span>}</h3>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card className="stat-card">
            <Statistic title="总意图数" value={m.counters?.total_intents ?? 0} prefix={<ThunderboltOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card">
            <Statistic
              title="成功率"
              value={(m.counters?.total_intents ?? 0) > 0
                ? Math.round(((m.counters?.completed_intents ?? 0) / (m.counters?.total_intents ?? 1)) * 100)
                : 100}
              suffix="%"
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card">
            <Statistic title="活跃 Worker" value={m.gauges?.active_agents ?? 0} prefix={<TeamOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card">
            <Statistic title="总负载" value={m.gauges?.total_load ?? 0} prefix={<ClockCircleOutlined />} />
          </Card>
        </Col>
      </Row>

      {/* 图表 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card title="Agent 负载分布">
            <ReactECharts
              option={{
                tooltip: { trigger: 'axis' },
                xAxis: { type: 'category', data: agents.map(a => a.agent_id) },
                yAxis: { type: 'value', name: '负载' },
                series: [{
                  type: 'bar',
                  data: agents.map(a => a.load),
                  itemStyle: { color: '#6366f1' },
                }],
              }}
              style={{ height: 250 }}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="吞吐量趋势">
            <ReactECharts
              option={{
                tooltip: { trigger: 'axis' },
                xAxis: {
                  type: 'category',
                  data: Array.from({ length: 10 }, (_, i) => `T-${i + 1}`),
                },
                yAxis: { type: 'value', name: '意图数' },
                series: [{
                  type: 'line',
                  data: Array.from({ length: 10 }, () => Math.floor(Math.random() * 5)),
                  smooth: true,
                  itemStyle: { color: '#52c41a' },
                  areaStyle: { color: 'rgba(82, 196, 26, 0.1)' },
                }],
              }}
              style={{ height: 250 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 实时事件流 */}
      <Card title="实时事件流" size="small" style={{ maxHeight: 250, overflow: 'auto' }}>
        <div className="event-console" style={{ height: 150 }}>
          {recentEvents.length === 0 && <div style={{ color: '#888' }}>暂无事件，执行工作流后将在此显示...</div>}
          {recentEvents.map((evt, i) => (
            <div key={i} className="event-line">
              <span className="event-time">[{new Date(evt.timestamp * 1000).toLocaleTimeString()}]</span>{' '}
              <span className="event-topic">{evt.topic}</span>{' '}
              {JSON.stringify(evt.data?.payload ?? evt.data).slice(0, 120)}
            </div>
          ))}
        </div>
      </Card>
    </div>
    </Spin>
  );
}