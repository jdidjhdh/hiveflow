import { useState, useCallback, useEffect } from 'react';
import { Card, Table, Input, Tag, Empty, Button, Modal, message, Row, Col } from 'antd';
import { DatabaseOutlined, SearchOutlined, EyeOutlined, EditOutlined, ReloadOutlined } from '@ant-design/icons';
import { useEngineStore } from '@/store/useEngineStore';
import { apiFetch } from '@/api';
import { useI18n } from '@/i18n';

interface KeyRow {
  key: string;
  type: string;
}

interface AuditEntry {
  agent: string;
  action: string;
  key: string;
  timestamp: number;
}

export default function BlackboardPage() {
  const { t } = useI18n();
  const engineMode = useEngineStore(s => s.mode);
  const engine = useEngineStore().getEngine();
  const [keys, setKeys] = useState<KeyRow[]>(() =>
    engineMode === 'mock' ? engine.getBlackboardKeys() : []
  );
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedValue, setSelectedValue] = useState<unknown>(null);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [search, setSearch] = useState('');
  const [editModal, setEditModal] = useState(false);
  const [editValue, setEditValue] = useState('');
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (engineMode === 'mock') {
      setKeys(engine.getBlackboardKeys());
      return;
    }
    setLoading(true);
    try {
      const data = await apiFetch('/api/blackboard/keys');
      setKeys((data.keys || []).map((k: KeyRow) => ({ key: k.key, type: k.type || 'unknown' })));
    } catch (e) {
      message.error(String(e));
    } finally {
      setLoading(false);
    }
  }, [engine, engineMode]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!selectedKey) {
      setSelectedValue(null);
      setAuditLog([]);
      return;
    }
    if (engineMode === 'mock') {
      setSelectedValue(engine.getBlackboardValue(selectedKey));
      setAuditLog(engine.getAuditLog().filter(e => e.key === selectedKey));
      return;
    }
    (async () => {
      try {
        const valData = await apiFetch(`/api/blackboard/keys/${encodeURIComponent(selectedKey)}`);
        setSelectedValue(valData.value);
        const auditData = await apiFetch(
          `/api/audit?key=${encodeURIComponent(selectedKey)}&limit=100`
        );
        setAuditLog(auditData.entries || []);
      } catch {
        setSelectedValue(null);
        setAuditLog([]);
      }
    })();
  }, [selectedKey, engine, engineMode]);

  const filteredKeys = keys.filter(k => !search || k.key.toLowerCase().includes(search.toLowerCase()));
  const permissions = engineMode === 'mock' && selectedKey
    ? engine.getBlackboardPermissions(selectedKey)
    : null;

  const handleEdit = async () => {
    try {
      const parsed = JSON.parse(editValue);
      if (engineMode === 'mock') {
        engine.setBlackboardValue(selectedKey!, parsed);
      } else {
        await apiFetch(`/api/blackboard/keys/${encodeURIComponent(selectedKey!)}`, {
          method: 'POST',
          body: JSON.stringify({ value: parsed }),
        });
      }
      setSelectedValue(parsed);
      await refresh();
      setEditModal(false);
      message.success(t('pages.blackboard.messages.valueUpdated'));
    } catch {
      message.error(t('pages.blackboard.messages.invalidJson'));
    }
  };

  return (
    <Row gutter={[16, 16]} style={{ height: '100%' }}>
      <Col xs={24} sm={24} md={8} lg={7} xl={6}>
        <Card
          title={t('pages.blackboard.keyList')}
          size="small"
          loading={loading}
          extra={
            <Button type="text" size="small" icon={<ReloadOutlined />} onClick={refresh} />
          }
        >
          <Input
            placeholder={t('pages.blackboard.searchKey')}
            prefix={<SearchOutlined />}
            size="small"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: '100%', marginBottom: 8 }}
          />
          {filteredKeys.length === 0 ? (
            <Empty description={t('pages.blackboard.noData')} />
          ) : (
            <div style={{ maxHeight: 'calc(100vh - 280px)', overflowY: 'auto' }}>
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
      </Col>

      <Col xs={24} sm={24} md={16} lg={17} xl={18} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Card
          title={selectedKey ? t('pages.blackboard.valueTitle', { key: selectedKey }) : t('pages.blackboard.selectKey')}
          size="small"
          extra={
            selectedKey && (
              <Button icon={<EditOutlined />} size="small" onClick={() => {
                setEditValue(JSON.stringify(selectedValue, null, 2));
                setEditModal(true);
              }}>{t('pages.blackboard.edit')}</Button>
            )
          }
        >
          {!selectedKey ? (
            <Empty description={t('pages.blackboard.selectKeyHint')} />
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
              {JSON.stringify(selectedValue, null, 2)}
            </pre>
          )}
        </Card>

        {permissions && (
          <Card title={t('pages.blackboard.permissions')} size="small">
            <p>
              <EyeOutlined style={{ color: '#1890ff' }} /> {t('pages.blackboard.readableAgents')}{' '}
              {permissions.readers.length > 0
                ? permissions.readers.map(a => <Tag key={a} color="blue">{a}</Tag>)
                : t('pages.blackboard.none')}
            </p>
            <p>
              <EditOutlined style={{ color: '#52c41a' }} /> {t('pages.blackboard.writableAgents')}{' '}
              {permissions.writers.length > 0
                ? permissions.writers.map(a => <Tag key={a} color="green">{a}</Tag>)
                : t('pages.blackboard.none')}
            </p>
          </Card>
        )}

        <Card title={t('pages.blackboard.auditLog')} size="small" extra={
          engineMode === 'real' ? <Tag color="green">{t('pages.blackboard.realAudit')}</Tag> : <Tag>{t('pages.blackboard.mockAudit')}</Tag>
        }>
          <Table
            dataSource={auditLog.slice(-50)}
            rowKey={(r, i) => `${r.agent}-${r.action}-${r.key}-${r.timestamp}-${i}`}
            size="small"
            pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total) => t('pages.blackboard.totalRecords', { count: total }) }}
            scroll={{ x: 600 }}
            columns={[
              {
                title: t('pages.blackboard.columns.time'), dataIndex: 'timestamp', width: 150,
                render: (ts: number) => new Date(ts * 1000).toLocaleTimeString(),
              },
              { title: t('pages.blackboard.columns.action'), dataIndex: 'action', width: 80, render: (a: string) => <Tag>{a}</Tag> },
              { title: t('pages.blackboard.columns.agent'), dataIndex: 'agent', ellipsis: true },
              { title: t('pages.blackboard.columns.key'), dataIndex: 'key', ellipsis: true },
            ]}
          />
        </Card>

        <Modal
          title={t('pages.blackboard.editModal', { key: selectedKey ?? '' })}
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
      </Col>
    </Row>
  );
}
