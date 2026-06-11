import { Drawer, Card, Table, Tag, Empty, Space, Button, Typography } from 'antd';
import { DownloadOutlined, CloseOutlined } from '@ant-design/icons';

export interface ExecutionResult {
  nodeId: string;
  label: string;
  status: 'completed' | 'failed';
  result?: Record<string, unknown>;
  error?: string;
  duration?: number;
}

interface ExecutionSummaryProps {
  open: boolean;
  onClose: () => void;
  results: ExecutionResult[];
  totalNodes: number;
}

export default function ExecutionSummaryPanel({
  open,
  onClose,
  results,
  totalNodes,
}: ExecutionSummaryProps) {
  const completedCount = results.filter(r => r.status === 'completed').length;
  const failedCount = results.filter(r => r.status === 'failed').length;
  const successRate = totalNodes > 0 ? Math.round((completedCount / totalNodes) * 100) : 0;

  const columns = [
    {
      title: '节点',
      dataIndex: 'label',
      key: 'label',
      width: 140,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => (
        <Tag color={status === 'completed' ? 'success' : 'error'}>
          {status === 'completed' ? '成功' : '失败'}
        </Tag>
      ),
    },
    {
      title: '耗时',
      dataIndex: 'duration',
      key: 'duration',
      width: 80,
      render: (d?: number) => d ? `${d.toFixed(2)}s` : '-',
    },
    {
      title: '结果',
      dataIndex: 'result',
      key: 'result',
      ellipsis: true,
      render: (result: Record<string, unknown> | undefined, record: ExecutionResult) => {
        if (record.error) {
          return <Typography.Text type="danger" ellipsis>{record.error}</Typography.Text>;
        }
        if (result) {
          return <Typography.Text ellipsis>{JSON.stringify(result).slice(0, 50)}</Typography.Text>;
        }
        return '-';
      },
    },
  ];

  const handleExport = () => {
    const data = JSON.stringify(results, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'execution-results.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Drawer
      title="执行结果摘要"
      open={open}
      onClose={onClose}
      width={600}
      extra={
        <Space>
          <Button
            icon={<DownloadOutlined />}
            onClick={handleExport}
            disabled={results.length === 0}
          >
            导出
          </Button>
          <Button icon={<CloseOutlined />} onClick={onClose}>关闭</Button>
        </Space>
      }
    >
      {/* 统计卡片 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space split={<span style={{ color: '#d9d9d9' }}>|</span>}>
          <span>总节点: <strong>{totalNodes}</strong></span>
          <span>成功: <strong style={{ color: '#52c41a' }}>{completedCount}</strong></span>
          <span>失败: <strong style={{ color: '#ff4d4f' }}>{failedCount}</strong></span>
          <span>成功率: <strong>{successRate}%</strong></span>
        </Space>
      </Card>

      {/* 结果表格 */}
      {results.length === 0 ? (
        <Empty description="暂无执行结果" />
      ) : (
        <Table<ExecutionResult>
          columns={columns}
          dataSource={results.map((r, i) => ({ ...r, key: i }))}
          size="small"
          pagination={false}
          scroll={{ y: 400 }}
        />
      )}
    </Drawer>
  );
}
