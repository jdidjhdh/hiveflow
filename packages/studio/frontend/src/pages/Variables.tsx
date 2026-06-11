import { useState, useCallback } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, Popconfirm, message, Typography, Empty, Alert,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, InfoCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useVariableStore } from '@/store/useVariableStore';
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
  const variables = useVariableStore((s) => s.variables);
  const addVariable = useVariableStore((s) => s.addVariable);
  const updateVariable = useVariableStore((s) => s.updateVariable);
  const deleteVariable = useVariableStore((s) => s.deleteVariable);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingVar, setEditingVar] = useState<VariableDef | null>(null);
  const [form] = Form.useForm();

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
          message.error('对象值必须是有效的 JSON');
          return;
        }
      } else if (values.type === 'array') {
        try {
          parsedValue = typeof values.value === 'string'
            ? JSON.parse(values.value)
            : values.value;
        } catch {
          message.error('数组值必须是有效的 JSON');
          return;
        }
      }

      if (editingVar) {
        updateVariable(editingVar.id, { ...values, value: parsedValue });
        message.success('变量已更新');
      } else {
        addVariable({ ...values, value: parsedValue });
        message.success('变量已添加');
      }
      setModalOpen(false);
    } catch (err) {
      console.error('Validation failed:', err);
    }
  }, [form, editingVar, addVariable, updateVariable]);

  const handleDelete = useCallback((id: string) => {
    deleteVariable(id);
    message.success('变量已删除');
  }, [deleteVariable]);

  const columns: ColumnsType<VariableDef> = [
    {
      title: '变量名',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <Text code strong>{text}</Text>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (type: string) => (
        <Tag color={typeColors[type] || 'default'}>{type}</Tag>
      ),
    },
    {
      title: '作用域',
      dataIndex: 'scope',
      key: 'scope',
      width: 100,
      render: (scope: string) => (
        <Tag color={scopeColors[scope] || 'default'}>{scope === 'global' ? '全局' : '局部'}</Tag>
      ),
    },
    {
      title: '值',
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
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (text?: string) => text || '-',
    },
    {
      title: '操作',
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
            编辑
          </Button>
          <Popconfirm
            title="确认删除"
            description={`确定要删除变量 "${record.name}" 吗？`}
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

  return (
    <div data-testid="variables-page" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0 }}>变量管理</h2>
          <p style={{ color: '#888', margin: '4px 0 0' }}>管理工作流中使用的变量，支持在节点中通过 <Text code>{`{{variable.name}}`}</Text> 引用</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} data-testid="btn-add-variable" onClick={() => handleOpenModal()}>
          新建变量
        </Button>
      </div>

      <Alert
        icon={<InfoCircleOutlined />}
        type="info"
        message="变量引用语法"
        description={
          <div style={{ fontSize: 13 }}>
            <p style={{ marginBottom: 4 }}>在节点配置中使用 <Text code>{`{{variable_name}}`}</Text> 语法引用变量：</p>
            <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
              <li>字符串: <Text code>{`{{api_url}}`}</Text> → <Text code>https://api.example.com</Text></li>
              <li>数字: <Text code>{`{{max_retries}}`}</Text> → <Text code>3</Text></li>
              <li>对象属性: <Text code>{`{{config.timeout}}`}</Text> → <Text code>30</Text></li>
            </ul>
          </div>
        }
        style={{ marginBottom: 16 }}
      />

      <Table<VariableDef>
        columns={columns}
        dataSource={variables}
        rowKey="id"
        pagination={{ pageSize: 10, showSizeChanger: true, showTotal: t => `共 ${t} 个变量` }}
        scroll={{ x: 800 }}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无变量，点击右上角按钮创建"
            />
          ),
        }}
      />

      <Modal
        title={editingVar ? '编辑变量' : '新建变量'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        width={500}
        okButtonProps={{ 'data-testid': 'btn-var-confirm' }}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="变量名"
            rules={[
              { required: true, message: '请输入变量名' },
              { pattern: /^[a-zA-Z_][a-zA-Z0-9_]*$/, message: '变量名只能包含字母、数字和下划线' },
            ]}
          >
            <Input data-testid="input-var-name" placeholder="例如: api_url, max_retries" />
          </Form.Item>

          <Form.Item name="type" label="类型" rules={[{ required: true }]}>
            <Select>
              <Select.Option value="string">字符串 (string)</Select.Option>
              <Select.Option value="number">数字 (number)</Select.Option>
              <Select.Option value="boolean">布尔值 (boolean)</Select.Option>
              <Select.Option value="object">对象 (object)</Select.Option>
              <Select.Option value="array">数组 (array)</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="value"
            label="值"
            rules={[{ required: true, message: '请输入变量值' }]}
          >
            <Input.TextArea
              data-testid="input-var-value"
              rows={3}
              placeholder="输入变量值（对象和数组请使用 JSON 格式）"
            />
          </Form.Item>

          <Form.Item name="scope" label="作用域">
            <Select>
              <Select.Option value="global">全局 (global)</Select.Option>
              <Select.Option value="local">局部 (local)</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input placeholder="变量用途说明" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
