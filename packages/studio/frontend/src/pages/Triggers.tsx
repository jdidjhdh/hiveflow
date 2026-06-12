import { useState, useCallback, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, Popconfirm,
  message, Switch, Card, Typography, Tooltip, Alert, Divider, Empty, Row, Col,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
  ThunderboltOutlined, ClockCircleOutlined, GlobalOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useTriggerStore } from '@/store/useTriggerStore';
import { useEngineStore } from '@/store/useEngineStore';
import { listTriggers, createTrigger, updateTriggerApi, deleteTriggerApi, toggleTriggerApi } from '@/api/triggers';
import { getPublicApiBaseUrl, getErrorMessage } from '@/api';
import ApiErrorAlert from '@/components/ApiErrorAlert';
import { DemoDataBanner } from '@/components/RealModeRequired';
import { useI18n } from '@/i18n';
import type { TriggerDef } from '@/types';

const { Text, Paragraph } = Typography;

const typeConfig: Record<string, { icon: JSX.Element; color: string; labelKey: 'webhook' | 'schedule' | 'event' }> = {
  webhook: { icon: <GlobalOutlined />, color: 'blue', labelKey: 'webhook' },
  schedule: { icon: <ClockCircleOutlined />, color: 'orange', labelKey: 'schedule' },
  event: { icon: <ThunderboltOutlined />, color: 'green', labelKey: 'event' },
};

const commonEvents = [
  'user.created', 'user.updated', 'user.deleted',
  'workflow.started', 'workflow.completed', 'workflow.failed',
  'task.assigned', 'task.completed',
  'data.imported', 'data.exported',
];

function triggerConfigDefaults(type: string): Record<string, unknown> {
  const base = getPublicApiBaseUrl();
  const defaults: Record<string, Record<string, unknown>> = {
    webhook: { method: 'POST', path: `${base}/api/webhook/{id}` },
    schedule: { cron: '0 */6 * * *', timezone: 'Asia/Shanghai' },
    event: { event_name: 'user.created' },
  };
  return defaults[type] || {};
}

function renderConfig(config: Record<string, unknown>, type: string): string {
  if (type === 'webhook') {
    return `URL: ${(config.url as string) || '-'}, Method: ${(config.method as string) || 'POST'}`;
  }
  if (type === 'schedule') {
    return `Cron: ${(config.cron as string) || '-'}, ${config.timezone ? `TZ: ${config.timezone}` : ''}`;
  }
  if (type === 'event') {
    return `Event: ${(config.event_name as string) || '-'}`;
  }
  return JSON.stringify(config);
}

export default function TriggersPage() {
  const { t } = useI18n();
  const engineMode = useEngineStore((s) => s.mode);
  const triggers = useTriggerStore((s) => s.triggers);
  const addTrigger = useTriggerStore((s) => s.addTrigger);
  const updateTrigger = useTriggerStore((s) => s.updateTrigger);
  const deleteTrigger = useTriggerStore((s) => s.deleteTrigger);
  const toggleTrigger = useTriggerStore((s) => s.toggleTrigger);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingTrigger, setEditingTrigger] = useState<TriggerDef | null>(null);
  const [form] = Form.useForm();
  const [triggerType, setTriggerType] = useState<string>('webhook');
  const [apiError, setApiError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadFromApi = useCallback(async () => {
    if (engineMode !== 'real') return;
    setLoading(true);
    setApiError(null);
    try {
      const items = await listTriggers();
      useTriggerStore.setState({ triggers: items });
    } catch (e) {
      setApiError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [engineMode]);

  useEffect(() => {
    void loadFromApi();
  }, [loadFromApi]);

  const handleOpenModal = useCallback((record?: TriggerDef, presetType?: string) => {
    if (record) {
      setEditingTrigger(record);
      setTriggerType(record.type);
      form.setFieldsValue({
        name: record.name,
        type: record.type,
        workflow_id: record.workflow_id,
        enabled: record.enabled,
        configJson: record.config,
      });
    } else {
      const type = presetType || 'webhook';
      setEditingTrigger(null);
      setTriggerType(type);
      form.resetFields();
      form.setFieldsValue({
        type,
        enabled: true,
        configJson: triggerConfigDefaults(type),
      });
    }
    setModalOpen(true);
  }, [form]);

  const handleTypeChange = useCallback((type: string) => {
    setTriggerType(type);
    form.setFieldsValue({ configJson: triggerConfigDefaults(type) });
  }, [form]);

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields();
      let parsedConfig: Record<string, unknown> = {};
      try {
        parsedConfig = typeof values.configJson === 'string'
          ? JSON.parse(values.configJson)
          : (values.configJson || {});
      } catch {
        message.error(t('pages.triggers.messages.invalidConfigJson'));
        return;
      }

      const base = getPublicApiBaseUrl();
      if (values.type === 'webhook' && !parsedConfig.url) {
        parsedConfig.url = `${base}/api/webhook/${editingTrigger?.id || 'new'}`;
      }

      if (engineMode === 'real') {
        try {
          if (editingTrigger) {
            await updateTriggerApi(editingTrigger.id, {
              name: values.name,
              type: values.type,
              config: parsedConfig,
              workflow_id: values.workflow_id,
            });
            message.success(t('pages.triggers.messages.updated'));
          } else {
            await createTrigger({
              name: values.name,
              type: values.type,
              config: parsedConfig,
              enabled: values.enabled ?? true,
              workflow_id: values.workflow_id,
            });
            message.success(t('pages.triggers.messages.added'));
          }
          setModalOpen(false);
          await loadFromApi();
        } catch (e) {
          message.error(getErrorMessage(e));
        }
        return;
      }

      if (editingTrigger) {
        updateTrigger(editingTrigger.id, {
          name: values.name,
          type: values.type,
          config: parsedConfig,
          workflow_id: values.workflow_id,
        });
        message.success(t('pages.triggers.messages.updated'));
      } else {
        addTrigger({
          name: values.name,
          type: values.type,
          config: parsedConfig,
          enabled: values.enabled ?? true,
          workflow_id: values.workflow_id,
        });
        message.success(t('pages.triggers.messages.added'));
      }
      setModalOpen(false);
    } catch (err) {
      console.error('Validation failed:', err);
    }
  }, [form, editingTrigger, addTrigger, updateTrigger, engineMode, loadFromApi, t]);

  const handleDelete = useCallback(async (id: string) => {
    if (engineMode === 'real') {
      try {
        await deleteTriggerApi(id);
        message.success(t('pages.triggers.messages.deleted'));
        await loadFromApi();
      } catch (e) {
        message.error(getErrorMessage(e));
      }
      return;
    }
    deleteTrigger(id);
    message.success(t('pages.triggers.messages.deleted'));
  }, [deleteTrigger, engineMode, loadFromApi, t]);

  const handleToggle = useCallback(async (id: string) => {
    if (engineMode === 'real') {
      try {
        await toggleTriggerApi(id);
        await loadFromApi();
      } catch (e) {
        message.error(getErrorMessage(e));
      }
      return;
    }
    toggleTrigger(id);
  }, [toggleTrigger, engineMode, loadFromApi]);

  const handleCopyWebhookUrl = useCallback((url: string) => {
    navigator.clipboard.writeText(url).then(() => {
      message.success(t('pages.triggers.messages.webhookCopied'));
    });
  }, []);

  const columns: ColumnsType<TriggerDef> = [
    {
      title: t('pages.triggers.columns.name'),
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: t('pages.triggers.columns.type'),
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type: string) => {
        const cfg = typeConfig[type] || typeConfig.webhook;
        return (
          <Tag color={cfg.color} icon={cfg.icon}>
            {t(`pages.triggers.types.${cfg.labelKey}`)}
          </Tag>
        );
      },
    },
    {
      title: t('pages.triggers.columns.config'),
      dataIndex: 'config',
      key: 'config',
      ellipsis: true,
      render: (config: Record<string, unknown>, record) => (
        <Text code>{renderConfig(config, record.type)}</Text>
      ),
    },
    {
      title: t('pages.triggers.columns.webhookUrl'),
      key: 'webhook_url',
      width: 200,
      render: (_: unknown, record: TriggerDef) => {
        if (record.type !== 'webhook') return '-';
        const url = (record.config.url as string) || '';
        return url ? (
          <Space>
            <Tooltip title={url}>
              <Text code style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', display: 'inline-block' }}>
                {url}
              </Text>
            </Tooltip>
            <Button type="link" size="small" icon={<CopyOutlined />} onClick={() => handleCopyWebhookUrl(url)} />
          </Space>
        ) : '-';
      },
    },
    {
      title: t('pages.triggers.columns.workflowId'),
      dataIndex: 'workflow_id',
      key: 'workflow_id',
      width: 150,
      render: (id?: string) => id ? <Text code>{id}</Text> : '-',
    },
    {
      title: t('pages.triggers.columns.status'),
      dataIndex: 'enabled',
      key: 'enabled',
      width: 100,
      render: (enabled: boolean) => (
        <Tag color={enabled ? 'success' : 'default'}>
          {enabled ? t('pages.triggers.status.enabled') : t('pages.triggers.status.disabled')}
        </Tag>
      ),
    },
    {
      title: t('pages.triggers.columns.actions'),
      key: 'action',
      width: 220,
      render: (_: unknown, record: TriggerDef) => (
        <Space>
          <Switch
            checked={record.enabled}
            onChange={() => handleToggle(record.id)}
            checkedChildren={t('pages.triggers.switch.on')}
            unCheckedChildren={t('pages.triggers.switch.off')}
            size="small"
          />
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleOpenModal(record)}
          >
            {t('pages.triggers.actions.edit')}
          </Button>
          <Popconfirm
            title={t('pages.triggers.confirmDelete')}
            description={t('pages.triggers.confirmDeleteDesc', { name: record.name })}
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              {t('pages.triggers.actions.delete')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const typeConfigs = [
    {
      type: 'webhook',
      icon: <GlobalOutlined style={{ fontSize: 24, color: '#1890ff' }} />,
      title: t('pages.triggers.typeCards.webhook.title'),
      description: t('pages.triggers.typeCards.webhook.description'),
      example: { url: 'https://your-server.com/webhook/{id}', method: 'POST' },
    },
    {
      type: 'schedule',
      icon: <ClockCircleOutlined style={{ fontSize: 24, color: '#fa8c16' }} />,
      title: t('pages.triggers.typeCards.schedule.title'),
      description: t('pages.triggers.typeCards.schedule.description'),
      example: { cron: '0 */6 * * *', timezone: 'Asia/Shanghai' },
    },
    {
      type: 'event',
      icon: <ThunderboltOutlined style={{ fontSize: 24, color: '#52c41a' }} />,
      title: t('pages.triggers.typeCards.event.title'),
      description: t('pages.triggers.typeCards.event.description'),
      example: { event_name: 'user.created' },
    },
  ];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <DemoDataBanner message={t('pages.triggers.demoBanner')} />
      <ApiErrorAlert error={apiError} onRetry={() => { void loadFromApi(); }} />
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0 }}>{t('pages.triggers.title')}</h2>
          <p style={{ color: '#888', margin: '4px 0 0' }}>{t('pages.triggers.subtitle')}</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          {t('pages.triggers.create')}
        </Button>
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {typeConfigs.map((tc) => (
          <Col xs={24} sm={12} md={8} key={tc.type}>
            <Card size="small" style={{ cursor: 'pointer', height: '100%' }} onClick={() => handleOpenModal(undefined, tc.type)}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                {tc.icon}
                <div>
                  <div style={{ fontWeight: 600 }}>{tc.title}</div>
                  <div style={{ fontSize: 12, color: '#888' }}>{tc.description}</div>
                </div>
              </div>
              <Paragraph
                copyable={{ text: JSON.stringify(tc.example) }}
                style={{ fontSize: 12, marginBottom: 0, background: '#fafafa', padding: '4px 8px', borderRadius: 4 }}
              >
                <Text code>{JSON.stringify(tc.example)}</Text>
              </Paragraph>
            </Card>
          </Col>
        ))}
      </Row>

      <Table<TriggerDef>
        columns={columns}
        dataSource={triggers}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total) => t('pages.triggers.totalCount', { count: total }) }}
        scroll={{ x: 1100 }}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={t('pages.triggers.empty')}
            />
          ),
        }}
      />

      <Modal
        title={editingTrigger ? t('pages.triggers.modal.editTitle') : t('pages.triggers.modal.createTitle')}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        width={650}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label={t('pages.triggers.form.name')} rules={[{ required: true }]}>
            <Input placeholder={t('pages.triggers.form.namePlaceholder')} />
          </Form.Item>

          <Form.Item name="type" label={t('pages.triggers.form.type')} rules={[{ required: true }]}>
            <Select onChange={handleTypeChange}>
              <Select.Option value="webhook">{t('pages.triggers.form.typeWebhook')}</Select.Option>
              <Select.Option value="schedule">{t('pages.triggers.form.typeSchedule')}</Select.Option>
              <Select.Option value="event">{t('pages.triggers.form.typeEvent')}</Select.Option>
            </Select>
          </Form.Item>

          {triggerType === 'webhook' && (
            <>
              <Alert
                message={t('pages.triggers.form.webhook.alertTitle')}
                description={t('pages.triggers.form.webhook.alertDesc')}
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
              />
              <Form.Item name={['configJson', 'method']} label={t('pages.triggers.form.webhook.method')}>
                <Select>
                  <Select.Option value="POST">POST</Select.Option>
                  <Select.Option value="GET">GET</Select.Option>
                  <Select.Option value="PUT">PUT</Select.Option>
                  <Select.Option value="PATCH">PATCH</Select.Option>
                </Select>
              </Form.Item>
              <Form.Item name={['configJson', 'path']} label={t('pages.triggers.form.webhook.path')}>
                <Input placeholder={t('pages.triggers.form.webhook.pathPlaceholder')} />
              </Form.Item>
              <Divider plain style={{ borderColor: '#d9d9d9' }}>{t('pages.triggers.form.webhook.bodyMappingDivider')}</Divider>
              <Form.Item name={['configJson', 'body_mapping']} label={t('pages.triggers.form.webhook.bodyMapping')}>
                <Input.TextArea rows={3} placeholder={t('pages.triggers.form.webhook.bodyMappingPlaceholder')} />
              </Form.Item>
            </>
          )}

          {triggerType === 'schedule' && (
            <>
              <Alert
                message={t('pages.triggers.form.schedule.alertTitle')}
                description={t('pages.triggers.form.schedule.alertDesc')}
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
              />
              <Form.Item name={['configJson', 'cron']} label={t('pages.triggers.form.schedule.cron')} rules={[{ required: true }]}>
                <Input placeholder={t('pages.triggers.form.schedule.cronPlaceholder')} />
              </Form.Item>
              <Form.Item name={['configJson', 'timezone']} label={t('pages.triggers.form.schedule.timezone')}>
                <Select>
                  <Select.Option value="Asia/Shanghai">Asia/Shanghai (UTC+8)</Select.Option>
                  <Select.Option value="UTC">UTC</Select.Option>
                  <Select.Option value="America/New_York">America/New_York (UTC-5)</Select.Option>
                </Select>
              </Form.Item>
            </>
          )}

          {triggerType === 'event' && (
            <>
              <Alert
                message={t('pages.triggers.form.event.alertTitle')}
                description={t('pages.triggers.form.event.alertDesc')}
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
              />
              <Form.Item name={['configJson', 'event_name']} label={t('pages.triggers.form.event.eventName')} rules={[{ required: true }]}>
                <Select
                  showSearch
                  placeholder={t('pages.triggers.form.event.eventNamePlaceholder')}
                  options={commonEvents.map((e) => ({ value: e, label: e }))}
                />
              </Form.Item>
              <Form.Item name={['configJson', 'filter']} label={t('pages.triggers.form.event.filter')}>
                <Input.TextArea rows={2} placeholder={t('pages.triggers.form.event.filterPlaceholder')} />
              </Form.Item>
            </>
          )}

          <Form.Item name="workflow_id" label={t('pages.triggers.form.workflowId')}>
            <Input placeholder={t('pages.triggers.form.workflowIdPlaceholder')} />
          </Form.Item>

          <Form.Item name="enabled" label={t('pages.triggers.form.enabled')} valuePropName="checked" initialValue={true}>
            <Switch checkedChildren={t('pages.triggers.switch.on')} unCheckedChildren={t('pages.triggers.switch.off')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
