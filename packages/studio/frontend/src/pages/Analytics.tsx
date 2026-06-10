import { useEffect, useState } from 'react';
import {
  Card, Row, Col, Statistic, Table, Tag, Space,
  Select, Empty, Spin, Divider, Typography, Tooltip,
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

const { Text } = Typography;

// ========== 趋势图 ==========
function TrendChart({ data }: { data: NonNullable<ReturnType<typeof useAnalyticsStore.getState>['data']>['trends'] }) {
  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: ['执行次数', '成功', '失败', '平均耗时(ms)'],
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
        name: '次数',
        minInterval: 1,
      },
      {
        type: 'value',
        name: '耗时(ms)',
      },
    ],
    series: [
      {
        name: '执行次数',
        type: 'bar',
        data: data.map((d) => d.executions),
        itemStyle: { color: '#6366f1' },
      },
      {
        name: '成功',
        type: 'bar',
        stack: 'status',
        data: data.map((d) => d.successes),
        itemStyle: { color: '#52c41a' },
      },
      {
        name: '失败',
        type: 'bar',
        stack: 'status',
        data: data.map((d) => d.failures),
        itemStyle: { color: '#ff4d4f' },
      },
      {
        name: '平均耗时(ms)',
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
  const columns: ColumnsType<NodeDurationRank> = [
    {
      title: '排名',
      key: 'rank',
      width: 60,
      render: (_, __, index) => {
        if (index === 0) return <TrophyOutlined style={{ color: '#faad14' }} />;
        return index + 1;
      },
    },
    {
      title: '节点名称',
      dataIndex: 'node_name',
      key: 'node_name',
    },
    {
      title: '调用次数',
      dataIndex: 'call_count',
      key: 'call_count',
      width: 100,
    },
    {
      title: '平均耗时',
      dataIndex: 'avg_duration',
      key: 'avg_duration',
      width: 120,
      render: (ms: number) => `${ms.toFixed(0)}ms`,
    },
    {
      title: '最大耗时',
      dataIndex: 'max_duration',
      key: 'max_duration',
      width: 120,
      render: (ms: number) => `${ms.toFixed(0)}ms`,
    },
    {
      title: '最小耗时',
      dataIndex: 'min_duration',
      key: 'min_duration',
      width: 120,
      render: (ms: number) => `${ms.toFixed(0)}ms`,
    },
    {
      title: '耗时分布',
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
      name: '执行次数',
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
  const option: EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical',
      left: 'left',
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          show: true,
          formatter: '{b}\n{d}%',
        },
        data: data.map((d, i) => ({
          value: d.count,
          name: d.error_type,
          itemStyle: {
            color: ['#ff4d4f', '#fa8c16', '#faad14', '#d9d9d9', '#8c8c8c'][i],
          },
        })),
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 300 }} />;
}

// ========== 主页面 ==========
export default function AnalyticsPage() {
  const { data, loading, timeRange, fetchAnalytics, setTimeRange } = useAnalyticsStore();

  useEffect(() => {
    fetchAnalytics(timeRange);
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" tip="加载分析数据..." />
      </div>
    );
  }

  if (!data) {
    return <Empty description="暂无分析数据" />;
  }

  const { summary, trends, node_rankings, agent_load, error_stats, recent_executions } = data;

  const execColumns: ColumnsType<(typeof recent_executions)[number]> = [
    {
      title: '执行 ID',
      dataIndex: 'id',
      key: 'id',
      width: 180,
      render: (id: string) => <Text copyable={{ text: id }}>{id.slice(-8)}</Text>,
    },
    {
      title: '工作流',
      dataIndex: 'workflow_id',
      key: 'workflow_id',
      width: 100,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config: Record<string, { color: string; icon: JSX.Element; label: string }> = {
          success: { color: 'success', icon: <CheckCircleOutlined />, label: '成功' },
          failed: { color: 'error', icon: <CloseCircleOutlined />, label: '失败' },
          timeout: { color: 'warning', icon: <ClockCircleOutlined />, label: '超时' },
        };
        const c = config[status] || config.success;
        return <Tag color={c.color} icon={c.icon}>{c.label}</Tag>;
      },
    },
    {
      title: '耗时',
      dataIndex: 'duration',
      key: 'duration',
      width: 100,
      render: (ms: number) => `${(ms / 1000).toFixed(1)}s`,
    },
    {
      title: '节点数',
      dataIndex: 'node_count',
      key: 'node_count',
      width: 80,
    },
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (ts: number) => new Date(ts).toLocaleString(),
    },
  ];

  return (
    <div>
      {/* 顶部控制栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h3 style={{ margin: 0 }}>执行分析</h3>
        <Space>
          <Text>时间范围：</Text>
          <Select
            value={timeRange}
            onChange={setTimeRange}
            options={[
              { value: 7, label: '最近 7 天' },
              { value: 30, label: '最近 30 天' },
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
              title="总执行次数"
              value={summary.total_executions}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: '#6366f1' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="成功率"
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
              title="平均耗时"
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
              title="失败次数"
              value={summary.failed_count}
              prefix={<CloseCircleOutlined />}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 执行趋势 */}
      <Card title="执行趋势" style={{ marginBottom: 16 }}>
        <TrendChart data={trends} />
      </Card>

      {/* 节点耗时排行 + Agent 负载 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="节点耗时排行" extra={<Tooltip title="按平均耗时降序排列"><TrophyOutlined /></Tooltip>}>
            <NodeRankingTable data={node_rankings} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="Agent 负载分布">
            <AgentLoadChart data={agent_load} />
          </Card>
        </Col>
      </Row>

      {/* 错误统计 + 最近执行 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card title="错误类型统计">
            <ErrorStatsChart data={error_stats} />
          </Card>
        </Col>
        <Col xs={24} lg={14}>
          <Card title="最近执行记录">
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
