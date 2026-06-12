import { useEffect } from 'react';
import {
  Card, Row, Col, Statistic, Table, Tag, Space,
  Select, Empty, Spin, Typography, Tooltip,
} from 'antd';
import {
  ThunderboltOutlined, CheckCircleOutlined,
  CloseCircleOutlined, ClockCircleOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import type { ColumnsType } from 'antd/es/table';
import type { NodeDurationRank, AgentLoadDist, ErrorTypeStat } from '@/types';
import { useAnalyticsStore } from '@/store/useAnalyticsStore';
import { useEngineStore } from '@/store/useEngineStore';
import ApiErrorAlert from '@/components/ApiErrorAlert';
import { DemoDataBanner } from '@/components/RealModeRequired';
import { useI18n } from '@/i18n';

const { Text } = Typography;

// ========== 趋势图 ==========
function TrendChart({ data }: { data: NonNullable<ReturnType<typeof useAnalyticsStore.getState>['data']>['trends'] }) {
  const { t } = useI18n();
  const executionsLabel = t('pages.analytics.trend.executions');
  const successLabel = t('pages.analytics.trend.success');
  const failedLabel = t('pages.analytics.trend.failed');
  const avgDurationLabel = t('pages.analytics.trend.avgDuration');

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: [executionsLabel, successLabel, failedLabel, avgDurationLabel],
      bottom: 0,
    },
    grid: {
      left: 50,
      right: 50,
      top: 30,
      bottom: 50,
    },
    xAxis: {
      type: 'category',
      data: data.map((d) => d.date.slice(5)),
      axisLabel: { rotate: 30 },
    },
    yAxis: [
      {
        type: 'value',
        name: t('pages.analytics.trend.countAxis'),
        minInterval: 1,
      },
      {
        type: 'value',
        name: t('pages.analytics.trend.durationAxis'),
      },
    ],
    series: [
      {
        name: executionsLabel,
        type: 'bar',
        data: data.map((d) => d.executions),
        itemStyle: { color: '#6366f1' },
      },
      {
        name: successLabel,
        type: 'bar',
        stack: 'status',
        data: data.map((d) => d.successes),
        itemStyle: { color: '#52c41a' },
      },
      {
        name: failedLabel,
        type: 'bar',
        stack: 'status',
        data: data.map((d) => d.failures),
        itemStyle: { color: '#ff4d4f' },
      },
      {
        name: avgDurationLabel,
        type: 'line',
        yAxisIndex: 1,
        data: data.map((d) => d.avg_duration),
        itemStyle: { color: '#fa8c16' },
        smooth: true,
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 350 }} />;
}

// ========== 节点耗时排行 ==========
function NodeRankingTable({ data }: { data: NodeDurationRank[] }) {
  const { t } = useI18n();

  const columns: ColumnsType<NodeDurationRank> = [
    {
      title: t('pages.analytics.nodeRanking.rank'),
      key: 'rank',
      width: 60,
      render: (_, __, index) => {
        if (index === 0) return <TrophyOutlined style={{ color: '#faad14' }} />;
        return index + 1;
      },
    },
    {
      title: t('pages.analytics.nodeRanking.nodeName'),
      dataIndex: 'node_name',
      key: 'node_name',
    },
    {
      title: t('pages.analytics.nodeRanking.callCount'),
      dataIndex: 'call_count',
      key: 'call_count',
      width: 100,
    },
    {
      title: t('pages.analytics.nodeRanking.avgDuration'),
      dataIndex: 'avg_duration',
      key: 'avg_duration',
      width: 120,
      render: (ms: number) => `${ms.toFixed(0)}ms`,
    },
    {
      title: t('pages.analytics.nodeRanking.maxDuration'),
      dataIndex: 'max_duration',
      key: 'max_duration',
      width: 120,
      render: (ms: number) => `${ms.toFixed(0)}ms`,
    },
    {
      title: t('pages.analytics.nodeRanking.minDuration'),
      dataIndex: 'min_duration',
      key: 'min_duration',
      width: 120,
      render: (ms: number) => `${ms.toFixed(0)}ms`,
    },
    {
      title: t('pages.analytics.nodeRanking.distribution'),
      key: 'distribution',
      render: (_, record) => {
        const range = record.max_duration - record.min_duration;
        const pct = range > 0 ? ((record.avg_duration - record.min_duration) / range) * 100 : 50;
        return (
          <div style={{ width: '100%', height: 8, background: '#f0f0f0', borderRadius: 4 }}>
            <div
              style={{
                width: `${pct}%`,
                height: '100%',
                background: '#1890ff',
                borderRadius: 4,
                transition: 'width 0.3s',
              }}
            />
          </div>
        );
      },
    },
  ];

  return <Table columns={columns} dataSource={data.slice(0, 10)} rowKey="node_name" pagination={false} size="small" />;
}

// ========== Agent 负载分布 ==========
function AgentLoadChart({ data }: { data: AgentLoadDist[] }) {
  const { t } = useI18n();

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    grid: {
      left: 120,
      right: 30,
      top: 20,
      bottom: 20,
    },
    xAxis: {
      type: 'value',
      name: t('pages.analytics.agentLoad.executionCount'),
    },
    yAxis: {
      type: 'category',
      data: data.map((d) => d.display_name).reverse(),
      axisLabel: { width: 100, overflow: 'truncate' },
    },
    series: [
      {
        type: 'bar',
        data: data.map((d) => d.execution_count).reverse(),
        itemStyle: {
          color: (params: any) => {
            const colors = ['#6366f1', '#52c41a', '#1890ff', '#fa8c16', '#722ed1', '#13c2c2'];
            return colors[params.dataIndex % colors.length];
          },
        },
        label: {
          show: true,
          position: 'right',
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 300 }} />;
}

// ========== 错误类型统计 ==========
function ErrorStatsChart({ data }: { data: ErrorTypeStat[] }) {
  const { t } = useI18n();

  // 错误类型颜色映射
  const errorColors: Record<string, string> = {
    '超时错误': '#ff4d4f',
    '连接失败': '#fa8c16',
    '响应异常': '#faad14',
    '资源耗尽': '#722ed1',
    '其他': '#d9d9d9',
    'Unknown': '#8c8c8c',
    'Runtime Error': '#ff7a45',
    'Validation Error': '#52c41a',
  };

  const totalCount = data.reduce((sum, d) => sum + d.count, 0);

  if (data.length === 0) {
    return <Empty description={t('pages.analytics.errorStats.noData')} style={{ padding: '40px 0' }} />;
  }

  const option: EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number; percent: number };
        return t('pages.analytics.errorStats.tooltip', {
          name: p.name,
          count: p.value,
          percent: p.percent,
        });
      },
    },
    series: [
      {
        type: 'pie',
        radius: ['50%', '70%'],
        center: ['50%', '55%'],
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          show: true,
          position: 'outside',
          formatter: (params: unknown) => {
            const p = params as { name: string; value: number };
            return `${p.name}\n${p.value}`;
          },
        },
        labelLine: {
          show: true,
          length: 15,
          length2: 10,
        },
        data: data.map((d) => ({
          value: d.count,
          name: d.error_type,
          itemStyle: {
            color: errorColors[d.error_type] || undefined,
          },
        })),
      },
    ],
  };

  return (
    <div>
      <ReactECharts option={option} style={{ height: 320 }} />
      <div style={{ marginTop: 8, textAlign: 'center', color: '#8c8c8c', fontSize: 12 }}>
        {t('pages.analytics.errorStats.totalErrors', { count: totalCount })}
      </div>
    </div>
  );
}

// ========== 主页面 ==========
export default function AnalyticsPage() {
  const { t } = useI18n();
  const { data, loading, error, timeRange, fetchAnalytics, setTimeRange } = useAnalyticsStore();
  const engineMode = useEngineStore(s => s.mode);

  useEffect(() => {
    fetchAnalytics(timeRange);
  }, [engineMode, fetchAnalytics, timeRange]);

  if (loading || !data) {
    if (loading) {
      return (
        <div style={{ textAlign: 'center', padding: 60, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <Spin size="large" />
          <span style={{ color: '#888', fontSize: 14 }}>{t('pages.analytics.loading')}</span>
        </div>
      );
    }
    return <Empty description={t('pages.analytics.noData')} />;
  }

  const { summary, trends, node_rankings, agent_load, error_stats, recent_executions } = data;

  const execColumns: ColumnsType<(typeof recent_executions)[number]> = [
    {
      title: t('pages.analytics.executions.id'),
      dataIndex: 'id',
      key: 'id',
      width: 180,
      render: (id: string) => <Text copyable={{ text: id }}>{id.slice(-8)}</Text>,
    },
    {
      title: t('pages.analytics.executions.workflow'),
      dataIndex: 'workflow_id',
      key: 'workflow_id',
      width: 100,
    },
    {
      title: t('pages.analytics.executions.status'),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config: Record<string, { color: string; icon: JSX.Element; label: string }> = {
          success: { color: 'success', icon: <CheckCircleOutlined />, label: t('pages.analytics.executions.success') },
          failed: { color: 'error', icon: <CloseCircleOutlined />, label: t('pages.analytics.executions.failed') },
          timeout: { color: 'warning', icon: <ClockCircleOutlined />, label: t('pages.analytics.executions.timeout') },
        };
        const c = config[status] || config.success;
        return <Tag color={c.color} icon={c.icon}>{c.label}</Tag>;
      },
    },
    {
      title: t('pages.analytics.executions.duration'),
      dataIndex: 'duration',
      key: 'duration',
      width: 100,
      render: (ms: number) => `${(ms / 1000).toFixed(1)}s`,
    },
    {
      title: t('pages.analytics.executions.nodeCount'),
      dataIndex: 'node_count',
      key: 'node_count',
      width: 80,
    },
    {
      title: t('pages.analytics.executions.time'),
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (ts: number) => new Date(ts).toLocaleString(),
    },
  ];

  return (
    <div>
      <DemoDataBanner message={t('pages.analytics.demoBanner')} />
      <ApiErrorAlert
        error={error && engineMode === 'real' ? error : null}
        onRetry={() => { void fetchAnalytics(timeRange); }}
      />
      {/* 顶部控制栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h3 style={{ margin: 0 }}>{t('pages.analytics.title')}</h3>
        <Space>
          <Text>{t('pages.analytics.timeRange')}</Text>
          <Select
            value={timeRange}
            onChange={setTimeRange}
            options={[
              { value: 7, label: t('pages.analytics.last7Days') },
              { value: 30, label: t('pages.analytics.last30Days') },
            ]}
            style={{ width: 120 }}
          />
        </Space>
      </div>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t('pages.analytics.stats.totalExecutions')}
              value={summary.total_executions}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: '#6366f1' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t('pages.analytics.stats.successRate')}
              value={summary.success_rate}
              precision={1}
              suffix="%"
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: summary.success_rate >= 90 ? '#52c41a' : summary.success_rate >= 70 ? '#faad14' : '#ff4d4f' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t('pages.analytics.stats.avgDuration')}
              value={summary.avg_duration / 1000}
              precision={2}
              suffix="s"
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t('pages.analytics.stats.failedCount')}
              value={summary.failed_count}
              prefix={<CloseCircleOutlined />}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 执行趋势 */}
      <Card title={t('pages.analytics.charts.executionTrend')} style={{ marginBottom: 16 }}>
        <TrendChart data={trends} />
      </Card>

      {/* 节点耗时排行 + Agent 负载 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <Card title={t('pages.analytics.charts.nodeRanking')} extra={<Tooltip title={t('pages.analytics.charts.nodeRankingTooltip')}><TrophyOutlined /></Tooltip>}>
            <NodeRankingTable data={node_rankings} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title={t('pages.analytics.charts.agentLoad')}>
            <AgentLoadChart data={agent_load} />
          </Card>
        </Col>
      </Row>

      {/* 错误统计 + 最近执行 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title={t('pages.analytics.charts.errorStats')}>
            <ErrorStatsChart data={error_stats} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title={t('pages.analytics.charts.recentExecutions')}>
            <Table
              columns={execColumns}
              dataSource={recent_executions}
              rowKey="id"
              pagination={{ pageSize: 5 }}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
