import { useState, useCallback, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, Popconfirm,
  message, Tabs, Card, Descriptions, InputNumber, Switch, Alert, Spin,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ApiOutlined,
  OpenAIOutlined, SettingOutlined, KeyOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useLLMConfigStore } from '@/store/useLLMConfigStore';
import { API_BASE_URL } from '@/utils/api';
import type { LLMProviderConfig, Credential } from '@/types';

const { TextArea } = Input;

const providerMeta: Record<string, { label: string; color: string; icon: JSX.Element; defaultBaseUrl: string }> = {
  openai: { label: 'OpenAI', color: 'green', icon: <OpenAIOutlined />, defaultBaseUrl: 'https://api.openai.com/v1' },
  anthropic: { label: 'Anthropic', color: 'purple', icon: <ApiOutlined />, defaultBaseUrl: 'https://api.anthropic.com/v1' },
  ollama: { label: 'Ollama', color: 'blue', icon: <ThunderboltOutlined />, defaultBaseUrl: 'http://localhost:11434' },
  custom: { label: '自定义', color: 'orange', icon: <SettingOutlined />, defaultBaseUrl: '' },
};

const defaultModels: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  anthropic: ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
  ollama: ['llama3', 'mistral', 'codellama', 'phi3'],
  custom: [],
};

export default function LLMConfigPage() {
  const providers = useLLMConfigStore((s) => s.providers);
  const addProvider = useLLMConfigStore((s) => s.addProvider);
  const updateProvider = useLLMConfigStore((s) => s.updateProvider);
  const deleteProvider = useLLMConfigStore((s) => s.deleteProvider);
  const listCredentials = useLLMConfigStore((s) => s.listCredentials);
  const createCredential = useLLMConfigStore((s) => s.createCredential);
  const testConnection = useLLMConfigStore((s) => s.testConnection);

  const [modalOpen, setModalOpen] = useState(false);
  const [credModalOpen, setCredModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<LLMProviderConfig | null>(null);
  const [form] = Form.useForm();
  const [credForm] = Form.useForm();
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [testing, setTesting] = useState(false);
  const [activeTab, setActiveTab] = useState('providers');

  useEffect(() => {
    if (activeTab === 'credentials') {
      listCredentials().then(setCredentials).catch(() => setCredentials([]));
    }
  }, [activeTab, listCredentials]);

  const handleOpenModal = useCallback((record?: LLMProviderConfig) => {
    if (record) {
      setEditingProvider(record);
      form.setFieldsValue(record);
    } else {
      setEditingProvider(null);
      form.resetFields();
      form.setFieldsValue({
        provider: 'openai',
        temperature: 0.7,
        max_tokens: 4096,
        top_p: 1,
      });
    }
    setModalOpen(true);
  }, [form]);

  const handleProviderChange = useCallback((provider: string) => {
    const meta = providerMeta[provider];
    if (meta && meta.defaultBaseUrl) {
      form.setFieldValue('base_url', meta.defaultBaseUrl);
    }
    form.setFieldValue('model_name', undefined);
  }, [form]);

  const handleSaveProvider = useCallback(async () => {
    try {
      const values = await form.validateFields();
      if (editingProvider) {
        updateProvider(editingProvider.id, values);
        message.success('模型配置已更新');
      } else {
        addProvider(values);
        message.success('模型配置已添加');
      }
      setModalOpen(false);
    } catch (err) {
      console.error('Validation failed:', err);
    }
  }, [form, editingProvider, addProvider, updateProvider]);

  const handleDeleteProvider = useCallback((id: string) => {
    deleteProvider(id);
    message.success('模型配置已删除');
  }, [deleteProvider]);

  const handleTestConnection = useCallback(async (provider: LLMProviderConfig) => {
    setTesting(true);
    try {
      const result = await testConnection(provider);
      if (result.success) {
        message.success(result.message);
      } else {
        message.warning(result.message);
      }
    } catch {
      message.error('测试连接失败');
    } finally {
      setTesting(false);
    }
  }, [testConnection]);

  const handleSaveCredential = useCallback(async () => {
    try {
      const values = await credForm.validateFields();
      await createCredential(values.name, values.type, values.value);
      message.success('凭证已创建');
      setCredModalOpen(false);
      credForm.resetFields();
      const creds = await listCredentials();
      setCredentials(creds);
    } catch (err) {
      console.error('Failed to save credential:', err);
    }
  }, [credForm, createCredential, listCredentials]);

  const handleDeleteCredential = useCallback(async (id: string) => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/credentials/${id}`, { method: 'DELETE' });
      if (resp.ok) {
        message.success('凭证已删除');
        setCredentials((prev) => prev.filter((c) => c.id !== id));
      }
    } catch {
      message.error('删除凭证失败');
    }
  }, []);

  const columns: ColumnsType<LLMProviderConfig> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
    },
    {
      title: '提供商',
      dataIndex: 'provider',
      key: 'provider',
      width: 120,
      render: (provider: string) => {
        const meta = providerMeta[provider] || providerMeta.custom;
        return <Tag color={meta.color} icon={meta.icon}>{meta.label}</Tag>;
      },
    },
    {
      title: '模型',
      dataIndex: 'model_name',
      key: 'model_name',
      width: 200,
    },
    {
      title: 'Temperature',
      dataIndex: 'temperature',
      key: 'temperature',
      width: 100,
      render: (v: number) => v?.toFixed(1),
    },
    {
      title: 'Max Tokens',
      dataIndex: 'max_tokens',
      key: 'max_tokens',
      width: 100,
    },
    {
      title: 'Base URL',
      dataIndex: 'base_url',
      key: 'base_url',
      ellipsis: true,
      render: (url?: string) => url ? <code style={{ fontSize: 11 }}>{url}</code> : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 240,
      render: (_: unknown, record: LLMProviderConfig) => (
        <Space>
          <Button
            type="primary"
            size="small"
            icon={testing ? <Spin size="small" /> : <ThunderboltOutlined />}
            loading={testing}
            onClick={() => handleTestConnection(record)}
          >
            测试
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确认删除"
            description={`确定要删除模型 "${record.name}" 吗？`}
            onConfirm={() => handleDeleteProvider(record.id)}
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const credColumns: ColumnsType<Credential> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 160, render: (v: string) => <code style={{ fontSize: 11 }}>{v}</code> },
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type: string) => <Tag icon={<KeyOutlined />}>{type}</Tag>,
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180, render: (t: number) => new Date(t * 1000).toLocaleString('zh-CN') },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: Credential) => (
        <Popconfirm title="确认删除" onConfirm={() => handleDeleteCredential(record.id)}>
          <Button type="link" danger size="small" icon={<DeleteOutlined />}>删除</Button>
        </Popconfirm>
      ),
    },
  ];

  const provider = Form.useWatch('provider', form);
  const availableModels = defaultModels[provider] || [];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0 }}>LLM 模型配置</h2>
          <p style={{ color: '#888', margin: '4px 0 0' }}>管理 AI 模型提供商、API 密钥和模型参数</p>
        </div>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'providers',
            label: '模型列表',
            children: (
              <>
                <div style={{ marginBottom: 16, display: 'flex', gap: 12 }}>
                  {Object.entries(providerMeta).map(([key, meta]) => (
                    <Card
                      key={key}
                      size="small"
                      style={{ flex: 1, cursor: 'pointer', borderColor: key === 'openai' ? '#52c41a' : undefined }}
                      onClick={() => {
                        form.setFieldsValue({ provider: key as any, base_url: meta.defaultBaseUrl });
                        handleOpenModal();
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {meta.icon}
                        <strong>{meta.label}</strong>
                      </div>
                      <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                        {(defaultModels[key] || []).length} 个预设模型
                      </div>
                    </Card>
                  ))}
                </div>

                <Table<LLMProviderConfig>
                  columns={columns}
                  dataSource={providers}
                  rowKey="id"
                  pagination={false}
                />
              </>
            ),
          },
          {
            key: 'credentials',
            label: '凭证管理',
            children: (
              <>
                <div style={{ marginBottom: 16 }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setCredModalOpen(true)}>
                    新建凭证
                  </Button>
                </div>
                <Alert
                  message="安全提示"
                  description="凭证值使用 Fernet 对称加密存储，仅在需要时自动解密。生产环境请使用环境变量设置 CREDENTIAL_KEY。"
                  type="info"
                  showIcon
                  style={{ marginBottom: 16 }}
                />
                <Table<Credential>
                  columns={credColumns}
                  dataSource={credentials}
                  rowKey="id"
                  pagination={false}
                />
              </>
            ),
          },
        ]}
      />

      {/* 模型配置 Modal */}
      <Modal
        title={editingProvider ? '编辑模型配置' : '新建模型配置'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSaveProvider}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="配置名称" rules={[{ required: true }]}>
            <Input placeholder="例如: 生产 GPT-4" />
          </Form.Item>

          <Form.Item name="provider" label="提供商" rules={[{ required: true }]}>
            <Select onChange={handleProviderChange}>
              <Select.Option value="openai">OpenAI</Select.Option>
              <Select.Option value="anthropic">Anthropic</Select.Option>
              <Select.Option value="ollama">Ollama</Select.Option>
              <Select.Option value="custom">自定义</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item name="model_name" label="模型名称" rules={[{ required: true }]}>
            <Select
              showSearch
              placeholder="选择或输入模型名称"
              options={availableModels.map((m) => ({ value: m, label: m }))}
            />
          </Form.Item>

          <Form.Item name="base_url" label="Base URL">
            <Input placeholder={providerMeta[provider]?.defaultBaseUrl || 'https://...'} />
          </Form.Item>

          <Form.Item name="api_key_credential_id" label="API Key 凭证">
            <Select
              placeholder="选择已保存的凭证"
              allowClear
              loading={credentials.length === 0}
              options={credentials.map((c) => ({ value: c.id, label: `${c.name} (${c.type})` }))}
              notFoundContent={
                <Button type="link" size="small" onClick={() => { setCredModalOpen(true); }}>
                  + 新建凭证
                </Button>
              }
            />
          </Form.Item>

          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="temperature" label="Temperature" style={{ flex: 1 }}>
              <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="max_tokens" label="Max Tokens" style={{ flex: 1 }}>
              <InputNumber min={1} max={128000} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="top_p" label="Top P" style={{ flex: 1 }}>
              <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
            </Form.Item>
          </div>
        </Form>
      </Modal>

      {/* 凭证 Modal */}
      <Modal
        title="新建凭证"
        open={credModalOpen}
        onCancel={() => setCredModalOpen(false)}
        onOk={handleSaveCredential}
        width={500}
      >
        <Form form={credForm} layout="vertical">
          <Form.Item name="name" label="凭证名称" rules={[{ required: true }]}>
            <Input placeholder="例如: OpenAI API Key" />
          </Form.Item>
          <Form.Item name="type" label="凭证类型" rules={[{ required: true }]} initialValue="api_key">
            <Select>
              <Select.Option value="api_key">API Key</Select.Option>
              <Select.Option value="oauth">OAuth Token</Select.Option>
              <Select.Option value="basic_auth">Basic Auth</Select.Option>
              <Select.Option value="custom">自定义</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="value" label="凭证值" rules={[{ required: true }]}>
            <TextArea rows={3} placeholder="sk-..." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
