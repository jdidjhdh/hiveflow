import { useState, useCallback, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, Popconfirm,
  message, Tabs, Card, InputNumber, Alert, Spin,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ApiOutlined,
  OpenAIOutlined, SettingOutlined, KeyOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useLLMConfigStore } from '@/store/useLLMConfigStore';
import { API_BASE_URL } from '@/api';
import type { LLMProviderConfig, Credential } from '@/types';
import PageMaturityNotice from '@/components/PageMaturityNotice';
import { useI18n } from '@/i18n';

const { TextArea } = Input;

const providerMeta: Record<string, { label: string; color: string; icon: JSX.Element; defaultBaseUrl: string }> = {
  openai: { label: 'OpenAI', color: 'green', icon: <OpenAIOutlined />, defaultBaseUrl: 'https://api.openai.com/v1' },
  anthropic: { label: 'Anthropic', color: 'purple', icon: <ApiOutlined />, defaultBaseUrl: 'https://api.anthropic.com/v1' },
  ollama: { label: 'Ollama', color: 'blue', icon: <ThunderboltOutlined />, defaultBaseUrl: 'http://localhost:11434' },
  custom: { label: '', color: 'orange', icon: <SettingOutlined />, defaultBaseUrl: '' },
};

const defaultModels: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  anthropic: ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
  ollama: ['llama3', 'mistral', 'codellama', 'phi3'],
  custom: [],
};

export default function LLMConfigPage() {
  const { t } = useI18n();
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

  const getProviderLabel = useCallback((provider: string) => {
    if (provider === 'custom' || !providerMeta[provider]) {
      return t('pages.llmConfig.providerMeta.custom');
    }
    return providerMeta[provider].label;
  }, [t]);

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
        message.success(t('pages.llmConfig.messages.providerUpdated'));
      } else {
        addProvider(values);
        message.success(t('pages.llmConfig.messages.providerAdded'));
      }
      setModalOpen(false);
    } catch (err) {
      console.error('Validation failed:', err);
    }
  }, [form, editingProvider, addProvider, updateProvider, t]);

  const handleDeleteProvider = useCallback((id: string) => {
    deleteProvider(id);
    message.success(t('pages.llmConfig.messages.providerDeleted'));
  }, [deleteProvider, t]);

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
      message.error(t('pages.llmConfig.messages.testFailed'));
    } finally {
      setTesting(false);
    }
  }, [testConnection, t]);

  const handleSaveCredential = useCallback(async () => {
    try {
      const values = await credForm.validateFields();
      await createCredential(values.name, values.type, values.value);
      message.success(t('pages.llmConfig.messages.credentialCreated'));
      setCredModalOpen(false);
      credForm.resetFields();
      const creds = await listCredentials();
      setCredentials(creds);
    } catch (err) {
      console.error('Failed to save credential:', err);
    }
  }, [credForm, createCredential, listCredentials, t]);

  const handleDeleteCredential = useCallback(async (id: string) => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/credentials/${id}`, { method: 'DELETE' });
      if (resp.ok) {
        message.success(t('pages.llmConfig.messages.credentialDeleted'));
        setCredentials((prev) => prev.filter((c) => c.id !== id));
      }
    } catch {
      message.error(t('pages.llmConfig.messages.deleteCredentialFailed'));
    }
  }, [t]);

  const columns: ColumnsType<LLMProviderConfig> = [
    {
      title: t('pages.llmConfig.columns.name'),
      dataIndex: 'name',
      key: 'name',
      width: 150,
    },
    {
      title: t('pages.llmConfig.columns.provider'),
      dataIndex: 'provider',
      key: 'provider',
      width: 120,
      render: (provider: string) => {
        const meta = providerMeta[provider] || providerMeta.custom;
        return <Tag color={meta.color} icon={meta.icon}>{getProviderLabel(provider)}</Tag>;
      },
    },
    {
      title: t('pages.llmConfig.columns.model'),
      dataIndex: 'model_name',
      key: 'model_name',
      width: 200,
    },
    {
      title: t('pages.llmConfig.columns.temperature'),
      dataIndex: 'temperature',
      key: 'temperature',
      width: 100,
      render: (v: number) => v?.toFixed(1),
    },
    {
      title: t('pages.llmConfig.columns.maxTokens'),
      dataIndex: 'max_tokens',
      key: 'max_tokens',
      width: 100,
    },
    {
      title: t('pages.llmConfig.columns.baseUrl'),
      dataIndex: 'base_url',
      key: 'base_url',
      ellipsis: true,
      render: (url?: string) => url ? <code style={{ fontSize: 11 }}>{url}</code> : '-',
    },
    {
      title: t('pages.llmConfig.columns.actions'),
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
            {t('pages.llmConfig.actions.test')}
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            {t('pages.llmConfig.actions.edit')}
          </Button>
          <Popconfirm
            title={t('pages.llmConfig.confirmDelete')}
            description={t('pages.llmConfig.confirmDeleteDesc', { name: record.name })}
            onConfirm={() => handleDeleteProvider(record.id)}
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              {t('pages.llmConfig.actions.delete')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const credColumns: ColumnsType<Credential> = [
    { title: t('pages.llmConfig.credColumns.id'), dataIndex: 'id', key: 'id', width: 160, render: (v: string) => <code style={{ fontSize: 11 }}>{v}</code> },
    { title: t('pages.llmConfig.credColumns.name'), dataIndex: 'name', key: 'name', width: 150 },
    {
      title: t('pages.llmConfig.credColumns.type'),
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type: string) => <Tag icon={<KeyOutlined />}>{type}</Tag>,
    },
    { title: t('pages.llmConfig.credColumns.createdAt'), dataIndex: 'created_at', key: 'created_at', width: 180, render: (tVal: number) => new Date(tVal * 1000).toLocaleString('zh-CN') },
    {
      title: t('pages.llmConfig.credColumns.actions'),
      key: 'action',
      width: 100,
      render: (_: unknown, record: Credential) => (
        <Popconfirm title={t('pages.llmConfig.confirmDeleteCredential')} onConfirm={() => handleDeleteCredential(record.id)}>
          <Button type="link" danger size="small" icon={<DeleteOutlined />}>{t('pages.llmConfig.actions.delete')}</Button>
        </Popconfirm>
      ),
    },
  ];

  const provider = Form.useWatch('provider', form);
  const availableModels = defaultModels[provider] || [];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <PageMaturityNotice pageKey="llmConfig" />
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0 }}>{t('pages.llmConfig.title')}</h2>
          <p style={{ color: '#888', margin: '4px 0 0' }}>{t('pages.llmConfig.subtitle')}</p>
        </div>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'providers',
            label: t('pages.llmConfig.tabs.providers'),
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
                        <strong>{getProviderLabel(key)}</strong>
                      </div>
                      <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                        {t('pages.llmConfig.presetModels', { count: (defaultModels[key] || []).length })}
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
            label: t('pages.llmConfig.tabs.credentials'),
            children: (
              <>
                <div style={{ marginBottom: 16 }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setCredModalOpen(true)}>
                    {t('pages.llmConfig.actions.createCredential')}
                  </Button>
                </div>
                <Alert
                  message={t('pages.llmConfig.securityAlert.title')}
                  description={t('pages.llmConfig.securityAlert.description')}
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
        title={editingProvider ? t('pages.llmConfig.modal.editProvider') : t('pages.llmConfig.modal.createProvider')}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSaveProvider}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label={t('pages.llmConfig.form.configName')} rules={[{ required: true }]}>
            <Input placeholder={t('pages.llmConfig.form.configNamePlaceholder')} />
          </Form.Item>

          <Form.Item name="provider" label={t('pages.llmConfig.form.provider')} rules={[{ required: true }]}>
            <Select onChange={handleProviderChange}>
              <Select.Option value="openai">OpenAI</Select.Option>
              <Select.Option value="anthropic">Anthropic</Select.Option>
              <Select.Option value="ollama">Ollama</Select.Option>
              <Select.Option value="custom">{t('pages.llmConfig.providerMeta.custom')}</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item name="model_name" label={t('pages.llmConfig.form.modelName')} rules={[{ required: true }]}>
            <Select
              showSearch
              placeholder={t('pages.llmConfig.form.modelNamePlaceholder')}
              options={availableModels.map((m) => ({ value: m, label: m }))}
            />
          </Form.Item>

          <Form.Item name="base_url" label={t('pages.llmConfig.form.baseUrl')}>
            <Input placeholder={providerMeta[provider]?.defaultBaseUrl || 'https://...'} />
          </Form.Item>

          <Form.Item name="api_key_credential_id" label={t('pages.llmConfig.form.apiKeyCredential')}>
            <Select
              placeholder={t('pages.llmConfig.form.selectCredential')}
              allowClear
              loading={credentials.length === 0}
              options={credentials.map((c) => ({ value: c.id, label: `${c.name} (${c.type})` }))}
              notFoundContent={
                <Button type="link" size="small" onClick={() => { setCredModalOpen(true); }}>
                  {t('pages.llmConfig.form.newCredential')}
                </Button>
              }
            />
          </Form.Item>

          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="temperature" label={t('pages.llmConfig.columns.temperature')} style={{ flex: 1 }}>
              <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="max_tokens" label={t('pages.llmConfig.columns.maxTokens')} style={{ flex: 1 }}>
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
        title={t('pages.llmConfig.modal.createCredential')}
        open={credModalOpen}
        onCancel={() => setCredModalOpen(false)}
        onOk={handleSaveCredential}
        width={500}
      >
        <Form form={credForm} layout="vertical">
          <Form.Item name="name" label={t('pages.llmConfig.form.credentialName')} rules={[{ required: true }]}>
            <Input placeholder={t('pages.llmConfig.form.credentialNamePlaceholder')} />
          </Form.Item>
          <Form.Item name="type" label={t('pages.llmConfig.form.credentialType')} rules={[{ required: true }]} initialValue="api_key">
            <Select>
              <Select.Option value="api_key">{t('pages.llmConfig.form.types.apiKey')}</Select.Option>
              <Select.Option value="oauth">{t('pages.llmConfig.form.types.oauth')}</Select.Option>
              <Select.Option value="basic_auth">{t('pages.llmConfig.form.types.basicAuth')}</Select.Option>
              <Select.Option value="custom">{t('pages.llmConfig.form.types.custom')}</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="value" label={t('pages.llmConfig.form.credentialValue')} rules={[{ required: true }]}>
            <TextArea rows={3} placeholder={t('pages.llmConfig.form.credentialValuePlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
