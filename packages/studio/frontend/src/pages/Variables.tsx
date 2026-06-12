import { useState, useCallback, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, Popconfirm, message, Typography, Empty, Alert,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, InfoCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useVariableStore } from '@/store/useVariableStore';
import { useEngineStore } from '@/store/useEngineStore';
import { listVariables, createVariable, updateVariableApi, deleteVariableApi } from '@/api/variables';
import { getErrorMessage } from '@/api';
import ApiErrorAlert from '@/components/ApiErrorAlert';
import { DemoDataBanner } from '@/components/RealModeRequired';
import { useI18n } from '@/i18n';
import type { VariableDef } from '@/types';

const { Text } = Typography;

const typeColors: Record<string, string> = {
  string: 'blue',
  number: 'green',
  boolean: 'orange',
  object: 'purple',
  array: 'cyan',
};

const scopeColors: Record<string, string> = {
  global: 'geekblue',
  local: 'volcano',
};

function renderValue(value: unknown, type: string): string {
  if (value === undefined || value === null) return '-';
  if (type === 'object' || type === 'array') {
    return JSON.stringify(value);
  }
  return String(value);
}

export default function VariablesPage() {
  const { t } = useI18n();
  const engineMode = useEngineStore((s) => s.mode);
  const variables = useVariableStore((s) => s.variables);
  const addVariable = useVariableStore((s) => s.addVariable);
  const updateVariable = useVariableStore((s) => s.updateVariable);
  const deleteVariable = useVariableStore((s) => s.deleteVariable);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingVar, setEditingVar] = useState<VariableDef | null>(null);
  const [form] = Form.useForm();
  const [apiError, setApiError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadFromApi = useCallback(async () => {
    if (engineMode !== 'real') return;
    setLoading(true);
    setApiError(null);
    try {
      const items = await listVariables();
      useVariableStore.setState({ variables: items });
    } catch (e) {
      setApiError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [engineMode]);

  useEffect(() => {
    void loadFromApi();
  }, [loadFromApi]);

  const handleOpenModal = useCallback((record?: VariableDef) => {
    if (record) {
      setEditingVar(record);
      form.setFieldsValue(record);
    } else {
      setEditingVar(null);
      form.resetFields();
      form.setFieldsValue({ type: 'string', scope: 'global' });
    }
    setModalOpen(true);
  }, [form]);

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields();
      // Parse value based on type
      let parsedValue = values.value;
      if (values.type === 'number') {
        parsedValue = Number(values.value);
      } else if (values.type === 'boolean') {
        parsedValue = values.value === 'true' || values.value === true;
      } else if (values.type === 'object') {
        try {
          parsedValue = typeof values.value === 'string'
            ? JSON.parse(values.value)
            : values.value;
        } catch {
          message.error(t('pages.variables.messages.invalidObjectJson'));
          return;
        }
      } else if (values.type === 'array') {
        try {
          parsedValue = typeof values.value === 'string'
            ? JSON.parse(values.value)
            : values.value;
        } catch {
          message.error(t('pages.variables.messages.invalidArrayJson'));
          return;
        }
      }

      if (engineMode === 'real') {
        try {
          if (editingVar) {
            await updateVariableApi(editingVar.name, {
              value: parsedValue,
              description: values.description,
              scope: values.scope,
            });
            message.success(t('pages.variables.messages.updated'));
          } else {
            await createVariable({
              name: values.name,
              type: values.type,
              value: parsedValue,
              scope: values.scope,
              description: values.description,
            });
            message.success(t('pages.variables.messages.added'));
          }
          setModalOpen(false);
          await loadFromApi();
        } catch (e) {
          message.error(getErrorMessage(e));
        }
        return;
      }

      if (editingVar) {
        updateVariable(editingVar.id, { ...values, value: parsedValue });
        message.success(t('pages.variables.messages.updated'));
      } else {
        addVariable({ ...values, value: parsedValue });
        message.success(t('pages.variables.messages.added'));
      }
      setModalOpen(false);
    } catch (err) {
      console.error('Validation failed:', err);
    }
  }, [form, editingVar, addVariable, updateVariable, engineMode, loadFromApi, t]);

  const handleDelete = useCallback(async (id: string) => {
    const target = useVariableStore.getState().variables.find((v) => v.id === id);
    if (engineMode === 'real' && target) {
      try {
        await deleteVariableApi(target.name);
        message.success(t('pages.variables.messages.deleted'));
        await loadFromApi();
      } catch (e) {
        message.error(getErrorMessage(e));
      }
      return;
    }
    deleteVariable(id);
    message.success(t('pages.variables.messages.deleted'));
  }, [deleteVariable, engineMode, loadFromApi, t]);

  const columns: ColumnsType<VariableDef> = [
    {
      title: t('pages.variables.columns.name'),
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <Text code strong>{text}</Text>
      ),
    },
    {
      title: t('pages.variables.columns.type'),
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (type: string) => (
        <Tag color={typeColors[type] || 'default'}>{type}</Tag>
      ),
    },
    {
      title: t('pages.variables.columns.scope'),
      dataIndex: 'scope',
      key: 'scope',
      width: 100,
      render: (scope: string) => (
        <Tag color={scopeColors[scope] || 'default'}>{scope === 'global' ? t('pages.variables.scope.global') : t('pages.variables.scope.local')}</Tag>
      ),
    },
    {
      title: t('pages.variables.columns.value'),
      dataIndex: 'value',
      key: 'value',
      ellipsis: true,
      render: (value: unknown, record) => (
        <Text copyable={{ text: renderValue(value, record.type) }}>
          {renderValue(value, record.type)}
        </Text>
      ),
    },
    {
      title: t('pages.variables.columns.description'),
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (text?: string) => text || '-',
    },
    {
      title: t('pages.variables.columns.actions'),
      key: 'action',
      width: 150,
      render: (_: unknown, record: VariableDef) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleOpenModal(record)}
          >
            {t('pages.variables.actions.edit')}
          </Button>
          <Popconfirm
            title={t('pages.variables.confirmDelete')}
            description={t('pages.variables.confirmDeleteDesc', { name: record.name })}
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              {t('pages.variables.actions.delete')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div data-testid="variables-page" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <DemoDataBanner message={t('pages.variables.demoBanner')} />
      <ApiErrorAlert error={apiError} onRetry={() => { void loadFromApi(); }} />
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0 }}>{t('pages.variables.title')}</h2>
          <p style={{ color: '#888', margin: '4px 0 0' }}>{t('pages.variables.subtitle')}</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} data-testid="btn-add-variable" onClick={() => handleOpenModal()}>
          {t('pages.variables.create')}
        </Button>
      </div>

      <Alert
        icon={<InfoCircleOutlined />}
        type="info"
        message={t('pages.variables.syntaxAlert.title')}
        description={
          <div style={{ fontSize: 13 }}>
            <p style={{ marginBottom: 4 }}>{t('pages.variables.syntaxAlert.intro')}</p>
            <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
              <li>{t('pages.variables.syntaxAlert.stringExample')}</li>
              <li>{t('pages.variables.syntaxAlert.numberExample')}</li>
              <li>{t('pages.variables.syntaxAlert.objectExample')}</li>
            </ul>
          </div>
        }
        style={{ marginBottom: 16 }}
      />

      <Table<VariableDef>
        columns={columns}
        dataSource={variables}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total) => t('pages.variables.totalCount', { count: total }) }}
        scroll={{ x: 800 }}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={t('pages.variables.empty')}
            />
          ),
        }}
      />

      <Modal
        title={editingVar ? t('pages.variables.modal.editTitle') : t('pages.variables.modal.createTitle')}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        width={500}
        okButtonProps={{ 'data-testid': 'btn-var-confirm' }}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label={t('pages.variables.form.name')}
            rules={[
              { required: true, message: t('pages.variables.form.nameRequired') },
              { pattern: /^[a-zA-Z_][a-zA-Z0-9_]*$/, message: t('pages.variables.form.namePattern') },
            ]}
          >
            <Input data-testid="input-var-name" placeholder={t('pages.variables.form.namePlaceholder')} />
          </Form.Item>

          <Form.Item name="type" label={t('pages.variables.form.type')} rules={[{ required: true }]}>
            <Select>
              <Select.Option value="string">{t('pages.variables.types.string')}</Select.Option>
              <Select.Option value="number">{t('pages.variables.types.number')}</Select.Option>
              <Select.Option value="boolean">{t('pages.variables.types.boolean')}</Select.Option>
              <Select.Option value="object">{t('pages.variables.types.object')}</Select.Option>
              <Select.Option value="array">{t('pages.variables.types.array')}</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="value"
            label={t('pages.variables.form.value')}
            rules={[{ required: true, message: t('pages.variables.form.valueRequired') }]}
          >
            <Input.TextArea
              data-testid="input-var-value"
              rows={3}
              placeholder={t('pages.variables.form.valuePlaceholder')}
            />
          </Form.Item>

          <Form.Item name="scope" label={t('pages.variables.form.scope')}>
            <Select>
              <Select.Option value="global">{t('pages.variables.scope.global')}</Select.Option>
              <Select.Option value="local">{t('pages.variables.scope.local')}</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item name="description" label={t('pages.variables.form.description')}>
            <Input placeholder={t('pages.variables.form.descriptionPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
