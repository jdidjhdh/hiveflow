import { useState, useCallback } from 'react';
import { Card, Table, Input, Tree, Tag, Empty, Button, Modal, message } from 'antd';
import { DatabaseOutlined, SearchOutlined, EyeOutlined, EditOutlined } from '@ant-design/icons';
import { useEngineStore } from '@/store/useEngineStore';

export default function BlackboardPage() {
  const engine = useEngineStore().getEngine();
  const [keys, setKeys] = useState(() => engine.getBlackboardKeys());
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [editModal, setEditModal] = useState(false);
  const [editValue, setEditValue] = useState('');

  const refresh = useCallback(() => {
    setKeys(engine.getBlackboardKeys());
  }, [engine]);

  const filteredKeys = keys.filter(k => !search || k.key.toLowerCase().includes(search.toLowerCase()));

  const value = selectedKey ? engine.getBlackboardValue(selectedKey) : null;
  const permissions = selectedKey ? engine.getBlackboardPermissions(selectedKey) : null;
  const auditLog = engine.getAuditLog().filter(e => e.key === selectedKey);

  const handleEdit = () => {
    try {
      const parsed = JSON.parse(editValue);
      engine.setBlackboardValue(selectedKey!, parsed);
      refresh();
      setEditModal(false);
      message.success('值已更新');
    } catch {
      message.error('无效的 JSON');
    }
  };

  return (
    <div style={{ display: 'flex', height: '100%', gap: 16 }}>
      {/* 左侧键列表 */}
      <div style={{ width: 280, flexShrink: 0 }}>
        <Card title="黑板键列表" size="small" extra={
          <Input
            placeholder="搜索键名"
            prefix={<SearchOutlined />}
            size="small"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: 150 }}
          />
        }>
          {filteredKeys.length === 0 ? (
            <Empty description="暂无数据" />
          ) : (
            <div style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}>
              {filteredKeys.map(k => (
                <div
                  key={k.key}
                  onClick={() => setSelectedKey(k.key)}
                  style={{
                    cursor: 'pointer',
                    padding: '8px 12px',
                    borderRadius: 6,
                    marginBottom: 4,
                    background: selectedKey === k.key ? '#f0f0ff' : undefined,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <span style={{ fontSize: 13, fontWeight: 500 }}>
                    <DatabaseOutlined style={{ marginRight: 6, color: '#6366f1' }} />
                    {k.key}
                  </span>
                  <Tag>{k.type}</Tag>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* 右侧详情 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Card
          title={selectedKey ? `值: ${selectedKey}` : '选择一个键查看'}
          size="small"
          extra={
            selectedKey && (
              <Button icon={<EditOutlined />} size="small" onClick={() => {
                setEditValue(JSON.stringify(value, null, 2));
                setEditModal(true);
              }}>编辑</Button>
            )
          }
        >
          {!selectedKey ? (
            <Empty description="请选择左侧键名" />
          ) : (
            <pre style={{
              background: '#1e1e1e',
              color: '#ce9178',
              padding: 16,
              borderRadius: 8,
              maxHeight: 300,
              overflow: 'auto',
              fontSize: 13,
            }}>
              {JSON.stringify(value, null, 2)}
            </pre>
          )}
        </Card>

        {/* 权限标签 */}
        {permissions && (
          <Card title="权限信息" size="small">
            <p>
              <EyeOutlined style={{ color: '#1890ff' }} /> 可读 Agent:{' '}
              {permissions.readers.length > 0
                ? permissions.readers.map(a => <Tag key={a} color="blue">{a}</Tag>)
                : '无'}
            </p>
            <p>
              <EditOutlined style={{ color: '#52c41a' }} /> 可写 Agent:{' '}
              {permissions.writers.length > 0
                ? permissions.writers.map(a => <Tag key={a} color="green">{a}</Tag>)
                : '无'}
            </p>
          </Card>
        )}

        {/* 审计日志 */}
        <Card title="审计日志" size="small">
          <Table
            dataSource={auditLog.slice(-50)}
            rowKey={(r) => `${r.agent}-${r.action}-${r.key}-${r.timestamp}`}
            size="small"
            pagination={false}
            columns={[
              {
                title: '时间', dataIndex: 'timestamp', width: 150,
                render: (t: number) => new Date(t * 1000).toLocaleTimeString(),
              },
              { title: '操作', dataIndex: 'action', width: 80, render: (a: string) => <Tag>{a}</Tag> },
              { title: 'Agent', dataIndex: 'agent' },
              { title: '键', dataIndex: 'key' },
            ]}
          />
        </Card>

        {/* 编辑弹窗 */}
        <Modal
          title={`编辑: ${selectedKey}`}
          open={editModal}
          onOk={handleEdit}
          onCancel={() => setEditModal(false)}
          width={600}
        >
          <Input.TextArea
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            rows={10}
            style={{ fontFamily: 'monospace', fontSize: 13 }}
          />
        </Modal>
      </div>
    </div>
  );
}