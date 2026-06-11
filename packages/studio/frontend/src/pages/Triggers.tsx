import { useState, useCallback } from 'react';
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
import { API_BASE_URL } from '@/utils/api';
import type { TriggerDef } from '@/types';

const { Text, Paragraph } = Typography;

const typeConfig: Record<string, { icon: JSX.Element; color: string; label: string }> = {
  webhook: { icon: <GlobalOutlined />, color: 'blue', label: 'Webhook' },
  schedule: { icon: <ClockCircleOutlined />, color: 'orange', label: '定时触发' },
  event: { icon: <ThunderboltOutlined />, color: 'green', label: '事件触发' },
};

const commonEvents = [
  'user.created', 'user.updated', 'user.deleted',
  'workflow.started', 'workflow.completed', 'workflow.failed',
  'task.assigned', 'task.completed',
  'data.imported', 'data.exported',
];

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
  const triggers = useTriggerStore((s) => s.triggers);
  const addTrigger = useTriggerStore((s) => s.addTrigger);
  const updateTrigger = useTriggerStore((s) => s.updateTrigger);
  const deleteTrigger = useTriggerStore((s) => s.deleteTrigger);
  const toggleTrigger = useTriggerStore((s) => s.toggleTrigger);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingTrigger, setEditingTrigger] = useState<TriggerDef | null>(null);
  const [form] = Form.useForm();
  const [triggerType, setTriggerType] = useState<string>('webhook');

  const handleOpenModal = useCallback((record?: TriggerDef) => {
    if (record) {
      setEditingTrigger(record);
      setTriggerType(record.type);
      form.setFieldsValue({
        ...record,
        configJson: JSON.stringify(record.config, null, 2),
      });
    } else {
      setEditingTrigger(null);
      setTriggerType('webhook');
      form.resetFields();
      form.setFieldsValue({
        type: 'webhook',
        enabled: true,
        method: 'POST',
        configJson: '{}',
      });
    }
    setModalOpen(true);
  }, [form]);

  const handleTypeChange = useCallback((type: string) => {
    setTriggerType(type);
    const defaults: Record<string, Record<string, unknown>> = {
      webhook: { method: 'POST', path: `${API_BASE_URL}/api/webhook/{id}` },
      schedule: { cron: '0 */6 * * *', timezone: 'Asia/Shanghai' },
      event: { event_name: 'user.created' },
    };
    form.setFieldsValue({ configJson: JSON.stringify(defaults[type] || {}, null, 2) });
  }, [form]);

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields();
      let parsedConfig: Record<string, unknown> = {};
      try {
        parsedConfig = typeof values.configJson === 'string'
          ? JSON.parse(values.configJson)
          : values.configJson;
      } catch {
        message.error('配置必须是有效的 JSON');
        return;
      }

      // Add webhook URL generation
      if (values.type === 'webhook' && !parsedConfig.url) {
        parsedConfig.url = `${API_BASE_URL}/api/webhook/${editingTrigger?.id || 'new'}`;
      }

      if (editingTrigger) {
        updateTrigger(editingTrigger.id, {
          name: values.name,
          type: values.type,
          config: parsedConfig,
          workflow_id: values.workflow_id,
        });
        message.success('触发器已更新');
      } else {
        addTrigger({
          name: values.name,
          type: values.type,
          config: parsedConfig,
          enabled: values.enabled ?? true,
          workflow_id: values.workflow_id,
        });
        message.success('触发器已添加');
      }
      setModalOpen(false);
    } catch (err) {
      console.error('Validation failed:', err);
    }
  }, [form, editingTrigger, addTrigger, updateTrigger]);

  const handleDelete = useCallback((id: string) => {
    deleteTrigger(id);
    message.success('触发器已删除');
  }, [deleteTrigger]);

  const handleToggle = useCallback((id: string) => {
    toggleTrigger(id);
  }, [toggleTrigger]);

  const handleCopyWebhookUrl = useCallback((url: string) => {
    navigator.clipboard.writeText(url).then(() => {
      message.success('Webhook URL 已复制到剪贴板');
    });
  }, []);

  const columns: ColumnsType<TriggerDef> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type: string) => {
        const cfg = typeConfig[type] || typeConfig.webhook;
        return (
          <Tag color={cfg.color} icon={cfg.icon}>
            {cfg.label}
          </Tag>
        );
      },
    },
    {
      title: '配置',
      dataIndex: 'config',
      key: 'config',
      ellipsis: true,
      render: (config: Record<string, unknown>, record) => (
        <Text code>{renderConfig(config, record.type)}</Text>
      ),
    },
    {
      title: 'Webhook URL',
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
      title: '关联工作流',
      dataIndex: 'workflow_id',
      key: 'workflow_id',
      width: 150,
      render: (id?: string) => id ? <Text code>{id}</Text> : '-',
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 100,
      render: (enabled: boolean) => (
        <Tag color={enabled ? 'success' : 'default'}>
          {enabled ? '已启用' : '已禁用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      render: (_: unknown, record: TriggerDef) => (
        <Space>
          <Switch
            checked={record.enabled}
            onChange={() => handleToggle(record.id)}
            checkedChildren="启用"
            unCheckedChildren="禁用"
            size="small"
          />
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleOpenModal(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除"
            description={`确定要删除触发器 "${record.name}" 吗？`}
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              删除
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
      title: 'Webhook 触发器',
      description: '通过 HTTP POST 请求触发工作流执行',
      example: { url: 'https://your-server.com/webhook/{id}', method: 'POST' },
    },
    {
      type: 'schedule',
      icon: <ClockCircleOutlined style={{ fontSize: 24, color: '#fa8c16' }} />,
      title: '定时触发器',
      description: '按照 Cron 表达式定时触发工作流',
      example: { cron: '0 */6 * * *', timezone: 'Asia/Shanghai' },
    },
    {
      type: 'event',
      icon: <ThunderboltOutlined style={{ fontSize: 24, color: '#52c41a' }} />,
      title: '事件触发器',
      description: '监听系统事件触发工作流',
      example: { event_name: 'user.created' },
    },
  ];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0 }}>触发器管理</h2>
          <p style={{ color: '#888', margin: '4px 0 0' }}>配置工作流的触发条件，支持 Webhook、定时任务和事件驱动</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          新建触发器
        </Button>
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {typeConfigs.map((tc) => (
          <Col xs={24} sm={12} md={8} key={tc.type}>
            <Card size="small" style={{ cursor: 'pointer', height: '100%' }} onClick={() => { form.resetFields(); handleTypeChange(tc.type); handleOpenModal(); }}>
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
        pagination={{ pageSize: 10, showSizeChanger: true, showTotal: t => `共 ${t} 条触发规则` }}
        scroll={{ x: 1100 }}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无触发器，点击右上角按钮创建"
            />
          ),
        }}
      />

      <Modal
        title={editingTrigger ? '编辑触发器' : '新建触发器'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        width={650}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="触发器名称" rules={[{ required: true }]}>
            <Input placeholder="例如: 每日数据同步、用户注册通知" />
          </Form.Item>

          <Form.Item name="type" label="触发器类型" rules={[{ required: true }]}>
            <Select onChange={handleTypeChange}>
              <Select.Option value="webhook">Webhook - HTTP 请求触发</Select.Option>
              <Select.Option value="schedule">Schedule - 定时触发</Select.Option>
              <Select.Option value="event">Event - 事件驱动触发</Select.Option>
            </Select>
          </Form.Item>

          {triggerType === 'webhook' && (
            <>
              <Alert
                message="Webhook 配置"
                description="配置接收 HTTP 请求的 URL 和方法。支持请求体映射到工作流变量。"
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
              />
              <Form.Item name={['configJson', 'method']} label="HTTP 方法">
                <Select>
                  <Select.Option value="POST">POST</Select.Option>
                  <Select.Option value="GET">GET</Select.Option>
                  <Select.Option value="PUT">PUT</Select.Option>
                  <Select.Option value="PATCH">PATCH</Select.Option>
                </Select>
              </Form.Item>
              <Form.Item name={['configJson', 'path']} label="Webhook 路径">
                <Input placeholder="/api/webhook/{id}" />
              </Form.Item>
              <Divider plain style={{ borderColor: '#d9d9d9' }}>请求体映射</Divider>
              <Form.Item name={['configJson', 'body_mapping']} label="请求体映射 (JSON)">
                <Input.TextArea rows={3} placeholder='{"input_data": "$.body.data", "action": "$.body.action"}' />
              </Form.Item>
            </>
          )}

          {triggerType === 'schedule' && (
            <>
              <Alert
                message="定时任务配置"
                description="使用 Cron 表达式定义执行时间。支持标准 5 位 Cron 语法。"
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
              />
              <Form.Item name={['configJson', 'cron']} label="Cron 表达式" rules={[{ required: true }]}>
                <Input placeholder="0 */6 * * *" />
              </Form.Item>
              <Form.Item name={['configJson', 'timezone']} label="时区">
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
                message="事件监听配置"
                description="选择要监听的事件类型。当事件触发时，自动执行关联的工作流。"
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
              />
              <Form.Item name={['configJson', 'event_name']} label="事件名称" rules={[{ required: true }]}>
                <Select
                  showSearch
                  placeholder="选择或输入事件名称"
                  options={commonEvents.map((e) => ({ value: e, label: e }))}
                />
              </Form.Item>
              <Form.Item name={['configJson', 'filter']} label="事件过滤 (JSON)">
                <Input.TextArea rows={2} placeholder='{"source": "user-service"}' />
              </Form.Item>
            </>
          )}

          <Form.Item name="workflow_id" label="关联工作流 ID">
            <Input placeholder="可选: 绑定到特定工作流" />
          </Form.Item>

          <Form.Item name="enabled" label="启用状态" valuePropName="checked" initialValue={true}>
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
