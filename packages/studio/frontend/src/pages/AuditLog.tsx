/**
 * HiveFlow - 审计日志面板
 *
 * 展示黑板操作的审计日志，包括：
 * - Agent 读写操作记录
 * - 操作时间线
 * - 按 Agent/Key 过滤
 * - 权限违规告警
 * - 操作统计
 */
import { useState, useCallback, useEffect } from 'react';
import {
  Table, Tag, Space, Select, Input, Button, Card, Statistic,
  Row, Col, Typography, Timeline, Badge, Tooltip, Popover,
  Alert,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  DatabaseOutlined, SearchOutlined,
  WarningOutlined, CheckCircleOutlined, StopOutlined,
  ClockCircleOutlined, UserOutlined, KeyOutlined,
  ReloadOutlined, ExportOutlined,
} from '@ant-design/icons';
import { apiFetch } from '@/api';
import PageMaturityNotice from '@/components/PageMaturityNotice';
import { useI18n } from '@/i18n';
import type { MessageKey } from '@/i18n';

const { Text } = Typography;

// Format timestamp to local string
function formatTimestamp(ts: number): string {
  return new Date(ts * 1000).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

// Extract hour from timestamp
function getHour(ts: number): string {
  const d = new Date(ts * 1000);
  return `${d.getHours().toString().padStart(2, '0')}:00`;
}

// ======================== Types ========================

interface AuditEntry {
  action: 'get' | 'put' | 'wait' | 'sys_get' | 'sys_wait' | 'sys_put' | 'sys_delete';
  agent: string;
  key: string;
  timestamp: number;
  permission_denied?: boolean;
  details?: string;
}

interface AuditStats {
  total_operations: number;
  read_count: number;
  write_count: number;
  wait_count: number;
  unique_agents: number;
  unique_keys: number;
  permission_denied_count: number;
  operations_by_agent: Record<string, number>;
  operations_by_hour: Record<string, number>;
}

const ACTION_META: Record<string, { color: string; icon: React.ReactNode; category: 'read' | 'write' | 'wait' | 'system' }> = {
  get:        { color: 'blue',   icon: <DatabaseOutlined />,  category: 'read' },
  put:        { color: 'green',  icon: <DatabaseOutlined />,  category: 'write' },
  wait:       { color: 'orange', icon: <ClockCircleOutlined />, category: 'wait' },
  sys_get:    { color: 'cyan',  icon: <DatabaseOutlined />,  category: 'system' },
  sys_wait:   { color: 'geekblue', icon: <ClockCircleOutlined />, category: 'system' },
  sys_put:    { color: 'lime',  icon: <DatabaseOutlined />,  category: 'system' },
  sys_delete: { color: 'red',   icon: <StopOutlined />,      category: 'system' },
};

const ACTION_LABEL_KEYS: Record<string, MessageKey> = {
  get: 'pages.auditLog.actions.get',
  put: 'pages.auditLog.actions.put',
  wait: 'pages.auditLog.actions.wait',
  sys_get: 'pages.auditLog.actions.sysGet',
  sys_wait: 'pages.auditLog.actions.sysWait',
  sys_put: 'pages.auditLog.actions.sysPut',
  sys_delete: 'pages.auditLog.actions.sysDelete',
};

// ======================== Stats Card ========================

function AuditStatsCard({ stats, loading }: { stats: AuditStats | null; loading: boolean }) {
  const { t } = useI18n();

  if (loading || !stats) return null;

  return (
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col span={4}>
        <Card>
          <Statistic title={t('pages.auditLog.stats.total')} value={stats.total_operations} prefix={<DatabaseOutlined />} />
        </Card>
      </Col>
      <Col span={4}>
        <Card>
          <Statistic title={t('pages.auditLog.stats.read')} value={stats.read_count} valueStyle={{ color: '#1890ff' }} />
        </Card>
      </Col>
      <Col span={4}>
        <Card>
          <Statistic title={t('pages.auditLog.stats.write')} value={stats.write_count} valueStyle={{ color: '#52c41a' }} />
        </Card>
      </Col>
      <Col span={4}>
        <Card>
          <Statistic title={t('pages.auditLog.stats.wait')} value={stats.wait_count} valueStyle={{ color: '#fa8c16' }} />
        </Card>
      </Col>
      <Col span={4}>
        <Card>
          <Statistic
            title={t('pages.auditLog.stats.activeAgents')}
            value={stats.unique_agents}
            prefix={<UserOutlined />}
          />
        </Card>
      </Col>
      <Col span={4}>
        <Card>
          <Statistic
            title={t('pages.auditLog.stats.permissionDenied')}
            value={stats.permission_denied_count}
            valueStyle={{ color: stats.permission_denied_count > 0 ? '#ff4d4f' : '#52c41a' }}
            prefix={stats.permission_denied_count > 0 ? <WarningOutlined /> : <CheckCircleOutlined />}
          />
        </Card>
      </Col>
    </Row>
  );
}

// ======================== Main Page ========================

export default function AuditLogPage() {
  const { t } = useI18n();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [filterAgent, setFilterAgent] = useState<string>();
  const [filterKey, setFilterKey] = useState<string>();
  const [filterAction, setFilterAction] = useState<string>();
  const [searchText, setSearchText] = useState('');

  const getActionLabel = useCallback((action: string) => {
    const key = ACTION_LABEL_KEYS[action];
    return key ? t(key) : action;
  }, [t]);

  const fetchAuditLog = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterAgent) params.set('agent', filterAgent);
      if (filterKey) params.set('key', filterKey);
      params.set('limit', '200');
      const data = await apiFetch(`/api/audit?${params}`);
      setEntries(data.entries || []);

      // Calculate stats
      const allEntries = data.entries || [];
      const statsData: AuditStats = {
        total_operations: allEntries.length,
        read_count: allEntries.filter((e: AuditEntry) => e.action === 'get' || e.action === 'sys_get').length,
        write_count: allEntries.filter((e: AuditEntry) => e.action === 'put' || e.action === 'sys_put').length,
        wait_count: allEntries.filter((e: AuditEntry) => e.action === 'wait' || e.action === 'sys_wait').length,
        unique_agents: new Set(allEntries.map((e: AuditEntry) => e.agent)).size,
        unique_keys: new Set(allEntries.map((e: AuditEntry) => e.key)).size,
        permission_denied_count: allEntries.filter((e: AuditEntry) => e.permission_denied).length,
        operations_by_agent: {},
        operations_by_hour: {},
      };

      allEntries.forEach((e: AuditEntry) => {
        statsData.operations_by_agent[e.agent] = (statsData.operations_by_agent[e.agent] || 0) + 1;
        const hour = getHour(e.timestamp);
        statsData.operations_by_hour[hour] = (statsData.operations_by_hour[hour] || 0) + 1;
      });

      setStats(statsData);
    } catch {
      // If API not available, show mock data
      setEntries([]);
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [filterAgent, filterKey]);

  useEffect(() => {
    fetchAuditLog();
  }, [fetchAuditLog]);

  const handleExport = useCallback(() => {
    const json = JSON.stringify(entries, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit-log-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [entries]);

  const filteredEntries = entries.filter(entry => {
    if (filterAction && entry.action !== filterAction) return false;
    if (searchText) {
      const q = searchText.toLowerCase();
      if (!entry.agent.toLowerCase().includes(q) && !entry.key.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const uniqueAgents = Array.from(new Set(entries.map(e => e.agent)));
  const uniqueKeys = Array.from(new Set(entries.map(e => e.key)));

  const columns: ColumnsType<AuditEntry> = [
    {
      title: t('pages.auditLog.columns.time'),
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (ts: number) => (
        <Space>
          <ClockCircleOutlined style={{ color: '#8c8c8c' }} />
          <Text style={{ fontSize: 12 }}>{formatTimestamp(ts)}</Text>
        </Space>
      ),
    },
    {
      title: t('pages.auditLog.columns.action'),
      dataIndex: 'action',
      key: 'action',
      width: 100,
      render: (action: string) => {
        const cfg = ACTION_META[action] || { color: 'default', icon: null, category: 'read' as const };
        return (
          <Tooltip title={action}>
            <Tag color={cfg.color} icon={cfg.icon}>{getActionLabel(action)}</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: t('pages.auditLog.columns.agent'),
      dataIndex: 'agent',
      key: 'agent',
      width: 150,
      render: (agent: string) => (
        <Tooltip title={agent}>
          <Space>
            <UserOutlined style={{ color: '#1890ff' }} />
            <Text ellipsis={{ tooltip: agent }} style={{ maxWidth: 120 }}>{agent}</Text>
          </Space>
        </Tooltip>
      ),
    },
    {
      title: t('pages.auditLog.columns.key'),
      dataIndex: 'key',
      key: 'key',
      width: 200,
      render: (key: string) => (
        <Tooltip title={key}>
          <Space>
            <KeyOutlined style={{ color: '#52c41a' }} />
            <Text ellipsis={{ tooltip: key }} style={{ maxWidth: 160, fontFamily: 'monospace', fontSize: 12 }}>{key}</Text>
          </Space>
        </Tooltip>
      ),
    },
    {
      title: t('pages.auditLog.columns.status'),
      key: 'status',
      width: 100,
      render: (_, record: AuditEntry) => (
        record.permission_denied
          ? <Badge status="error" text={t('pages.auditLog.status.denied')} />
          : <Badge status="success" text={t('pages.auditLog.status.success')} />
      ),
    },
    {
      title: t('pages.auditLog.columns.details'),
      dataIndex: 'details',
      key: 'details',
      render: (details: string) => details ? (
        <Popover content={<pre style={{ maxWidth: 300, maxHeight: 200, overflow: 'auto', fontSize: 12 }}>{details}</pre>}>
          <Text type="secondary" ellipsis style={{ maxWidth: 200 }}>{details}</Text>
        </Popover>
      ) : '-',
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <PageMaturityNotice pageKey="auditLog" />
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Typography.Title level={4} style={{ margin: 0 }}>{t('pages.auditLog.title')}</Typography.Title>
          <Text type="secondary">{t('pages.auditLog.subtitle')}</Text>
        </Space>
        <Space>
          <Button icon={<ExportOutlined />} onClick={handleExport}>{t('pages.auditLog.export')}</Button>
          <Button icon={<ReloadOutlined />} onClick={fetchAuditLog}>{t('pages.auditLog.refresh')}</Button>
        </Space>
      </div>

      {/* Stats */}
      <AuditStatsCard stats={stats} loading={loading} />

      {/* Permission Warning */}
      {stats && stats.permission_denied_count > 0 && (
        <Alert
          message={t('pages.auditLog.permissionAlert.title')}
          description={t('pages.auditLog.permissionAlert.description', { count: stats.permission_denied_count })}
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Filters */}
      <Card title={t('pages.auditLog.filters.title')} style={{ marginBottom: 16 }} size="small">
        <Space wrap>
          <Input
            placeholder={t('pages.auditLog.filters.searchPlaceholder')}
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
            style={{ width: 250 }}
          />
          <Select
            placeholder={t('pages.auditLog.filters.allAgents')}
            value={filterAgent}
            onChange={setFilterAgent}
            allowClear
            style={{ width: 180 }}
            options={uniqueAgents.map(a => ({ label: a, value: a }))}
          />
          <Select
            placeholder={t('pages.auditLog.filters.allKeys')}
            value={filterKey}
            onChange={setFilterKey}
            allowClear
            style={{ width: 180 }}
            options={uniqueKeys.map(k => ({ label: k, value: k }))}
          />
          <Select
            placeholder={t('pages.auditLog.filters.allActions')}
            value={filterAction}
            onChange={setFilterAction}
            allowClear
            style={{ width: 150 }}
            options={Object.keys(ACTION_META).map((k) => ({ label: getActionLabel(k), value: k }))}
          />
        </Space>
      </Card>

      {/* Agent Activity Summary */}
      {stats && Object.keys(stats.operations_by_agent).length > 0 && (
        <Card title={t('pages.auditLog.agentActivity')} style={{ marginBottom: 16 }} size="small">
          <Space wrap>
            {Object.entries(stats.operations_by_agent)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 10)
              .map(([agent, count]) => (
                <Tag
                  key={agent}
                  color="blue"
                  style={{ cursor: 'pointer' }}
                  onClick={() => setFilterAgent(agent)}
                >
                  {t('pages.auditLog.agentActivityCount', { agent, count })}
                </Tag>
              ))}
          </Space>
        </Card>
      )}

      {/* Audit Log Table */}
      <Card title={t('pages.auditLog.records')} size="small">
        <Table<AuditEntry>
          columns={columns}
          dataSource={filteredEntries}
          rowKey={(record) => `${record.timestamp}-${record.agent}-${record.key}`}
          loading={loading}
          pagination={{ pageSize: 20, showTotal: (total) => t('pages.auditLog.totalRecords', { count: total }) }}
          size="small"
          scroll={{ y: 500 }}
        />
      </Card>

      {/* Recent Activity Timeline */}
      {filteredEntries.length > 0 && (
        <Card title={t('pages.auditLog.timeline.title')} style={{ marginTop: 16 }} size="small">
          <Timeline
            items={filteredEntries.slice(0, 10).map(entry => {
              const cfg = ACTION_META[entry.action] || { color: 'blue', icon: null, category: 'read' as const };
              return {
                color: entry.permission_denied ? 'red' : cfg.color,
                children: (
                  <Space direction="vertical" size={0}>
                    <Space>
                      <Tag color={cfg.color}>{getActionLabel(entry.action)}</Tag>
                      <Text strong>{entry.agent}</Text>
                      <Text type="secondary">{t('pages.auditLog.timeline.operated')}</Text>
                      <Text code>{entry.key}</Text>
                    </Space>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {formatTimestamp(entry.timestamp)}
                    </Text>
                  </Space>
                ),
              };
            })}
          />
        </Card>
      )}
    </div>
  );
}
