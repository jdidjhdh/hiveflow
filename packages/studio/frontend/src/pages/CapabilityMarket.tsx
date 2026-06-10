/**
 * HiveFlow - 能力市场 / 插件市场
 *
 * 功能：
 * - 浏览插件市场（Marketplace）
 * - 管理我的能力（My Capabilities）
 * - 创建/编辑/删除外部服务能力
 * - 安装/卸载插件
 * - 导入/导出能力定义
 * - 搜索和分类过滤
 */
import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  Table, Tag, Button, Space, Input, App, Popconfirm, Modal, Form,
  Select, Tabs, Card, Statistic, Row, Col, Tooltip, Typography,
  Descriptions, Alert, Upload, message as msg, Divider, Badge,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  SearchOutlined, ApiOutlined, CodeOutlined,
  CloudServerOutlined, UploadOutlined, DeleteOutlined,
  SendOutlined, EditOutlined, PlusOutlined, DownloadOutlined,
  InboxOutlined, ShopOutlined, CheckCircleOutlined,
  ExportOutlined, ImportOutlined, EyeOutlined,
} from '@ant-design/icons';
import type { CapabilityDef, CapabilitySource } from '@/types';
import { API_BASE_URL, apiFetch, getErrorMessage } from '@/utils/api';

const { Text } = Typography;
const { TextArea } = Input;

const SOURCE_CONFIG: Record<CapabilitySource, { label: string; color: string; icon: React.ReactNode }> = {
  preset:            { label: '系统预置',  color: 'blue',   icon: <CloudServerOutlined /> },
  external_service:  { label: '外部服务',  color: 'green',  icon: <ApiOutlined /> },
  upload:            { label: '上传文件',  color: 'orange', icon: <UploadOutlined /> },
  online_edit:       { label: '在线编写',  color: 'purple', icon: <CodeOutlined /> },
};

// ======================== Types ========================

interface PluginMarketplaceItem {
  plugin_id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  author: string;
  status: 'available' | 'installed';
  tags: string[];
  created_at: number;
}

interface MarketplaceStats {
  total: number;
  by_category: Record<string, number>;
}

// ======================== Marketplace Tab ========================

function MarketplaceTab() {
  const { message } = App.useApp();
  const [plugins, setPlugins] = useState<PluginMarketplaceItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [categories, setCategories] = useState<Record<string, string>>({});
  const [selectedCategory, setSelectedCategory] = useState<string>();
  const [searchText, setSearchText] = useState('');
  const [stats, setStats] = useState<MarketplaceStats | null>(null);

  const fetchMarketplace = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedCategory) params.set('category', selectedCategory);
      if (searchText) params.set('q', searchText);
      const data = await apiFetch(`/api/plugins/marketplace?${params}`);
      setPlugins(data.plugins || []);
      setStats(data.stats);
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [selectedCategory, searchText]);

  const fetchCategories = useCallback(async () => {
    try {
      const data = await apiFetch('/api/plugins/marketplace/categories');
      setCategories(data.categories || {});
    } catch {
      // Ignore if not available
    }
  }, []);

  useEffect(() => {
    fetchMarketplace();
    fetchCategories();
  }, [fetchMarketplace, fetchCategories]);

  const handleInstall = useCallback(async (plugin: PluginMarketplaceItem) => {
    try {
      await apiFetch('/api/plugins/install', {
        method: 'POST',
        body: JSON.stringify({ plugin_id: plugin.plugin_id }),
      });
      message.success(`插件 "${plugin.name}" 已安装`);
      fetchMarketplace();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [fetchMarketplace]);

  const columns: ColumnsType<PluginMarketplaceItem> = [
    {
      title: '插件名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string, record: PluginMarketplaceItem) => (
        <Space direction="vertical" size={0}>
          <Space>
            <ShopOutlined />
            <Text strong>{name}</Text>
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>v{record.version} · {record.author}</Text>
        </Space>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (cat: string) => <Tag color="blue">{categories[cat] || cat}</Tag>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 200,
      render: (tags: string[]) => (
        <Space wrap>
          {tags.slice(0, 3).map((t) => <Tag key={t}>{t}</Tag>)}
          {tags.length > 3 && <Tag>+{tags.length - 3}</Tag>}
        </Space>
      ),
    },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (_, record: PluginMarketplaceItem) => (
        record.status === 'installed'
          ? <Tag color="green" icon={<CheckCircleOutlined />}>已安装</Tag>
          : <Tag color="default">未安装</Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, record: PluginMarketplaceItem) => (
        <Space>
          {record.status !== 'installed' && (
            <Button
              size="small"
              type="primary"
              icon={<DownloadOutlined />}
              onClick={() => handleInstall(record)}
            >
              安装
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      {/* Stats */}
      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card>
              <Statistic title="插件总数" value={stats.total} prefix={<ShopOutlined />} />
            </Card>
          </Col>
          {Object.entries(stats.by_category || {}).slice(0, 3).map(([cat, count]) => (
            <Col span={6} key={cat}>
              <Card>
                <Statistic title={categories[cat] || cat} value={count} />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* Filters */}
      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索插件..."
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          onPressEnter={fetchMarketplace}
          allowClear
          style={{ width: 250 }}
        />
        <Select
          placeholder="所有分类"
          value={selectedCategory}
          onChange={setSelectedCategory}
          allowClear
          style={{ width: 150 }}
          options={Object.entries(categories).map(([k, v]) => ({ label: v, value: k }))}
        />
        <Button onClick={fetchMarketplace}>刷新</Button>
      </Space>

      <Table
        columns={columns}
        dataSource={plugins}
        rowKey="plugin_id"
        loading={loading}
        pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 个插件` }}
      />
    </div>
  );
}

// ======================== My Capabilities Tab ========================

function MyCapabilitiesTab() {
  const { message } = App.useApp();
  const [caps, setCaps] = useState<CapabilityDef[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingCap, setEditingCap] = useState<CapabilityDef | null>(null);
  const [form] = Form.useForm();
  const [search, setSearch] = useState('');
  const [filterSource, setFilterSource] = useState<CapabilitySource | undefined>();

  const fetchCaps = useCallback(async () => {
    setLoading(true);
    try {
      // Try to fetch from backend, fallback to localStorage
      const data = await apiFetch('/api/capabilities');
      setCaps(data.capabilities || []);
    } catch {
      const stored = localStorage.getItem('hf_capabilities');
      if (stored) setCaps(JSON.parse(stored));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCaps();
  }, [fetchCaps]);

  const saveToStorage = useCallback((updated: CapabilityDef[]) => {
    localStorage.setItem('hf_capabilities', JSON.stringify(updated));
  }, []);

  const handleOpenModal = useCallback((cap?: CapabilityDef) => {
    if (cap) {
      setEditingCap(cap);
      form.setFieldsValue({
        name: cap.name,
        description: cap.description,
        source: cap.source,
        url: cap.config?.url,
        method: cap.config?.method,
        headers: cap.config?.headers?.map(h => `${h.key}: ${h.value}`).join('\n'),
        body: cap.config?.body,
        output_mapping: cap.config?.output_mapping,
        blackboard_key: cap.config?.blackboard_key,
        timeout: cap.config?.timeout,
        code: cap.code,
      });
    } else {
      setEditingCap(null);
      form.resetFields();
      form.setFieldValue('source', 'external_service');
      form.setFieldValue('method', 'GET');
      form.setFieldValue('timeout', 5);
    }
    setModalOpen(true);
  }, [form]);

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const now = Date.now() / 1000;

      let config: any = undefined;
      let code: string | undefined;

      if (values.source === 'external_service') {
        const headerLines = (values.headers || '').split('\n').filter(Boolean);
        config = {
          service_name: values.name,
          method: values.method,
          url: values.url,
          headers: headerLines.map((l: string) => {
            const [key, ...rest] = l.split(':');
            return { key: key.trim(), value: rest.join(':').trim() };
          }),
          body: values.body || '',
          output_mapping: values.output_mapping || '$.data',
          blackboard_key: values.blackboard_key || 'result',
          timeout: values.timeout || 5,
        };
      } else if (values.source === 'online_edit') {
        code = values.code;
      }

      const newCap: CapabilityDef = {
        id: editingCap?.id || `cap-${Date.now()}`,
        name: values.name,
        source: values.source,
        description: values.description || '',
        created_at: editingCap?.created_at || now,
        agent_count: editingCap?.agent_count || 0,
        config,
        code,
      };

      const updated = editingCap
        ? caps.map(c => c.id === editingCap.id ? newCap : c)
        : [newCap, ...caps];

      setCaps(updated);
      saveToStorage(updated);
      setModalOpen(false);
      message.success(editingCap ? '能力已更新' : '能力已创建');
    } catch (err: unknown) {
      if (err instanceof Error && err.message !== 'validateFields') {
        message.error(getErrorMessage(err));
      }
    }
  }, [form, editingCap, caps, saveToStorage]);

  const handleDelete = useCallback((id: string) => {
    const updated = caps.filter(c => c.id !== id);
    setCaps(updated);
    saveToStorage(updated);
    message.success('能力已删除');
  }, [caps, saveToStorage]);

  const handleExport = useCallback(() => {
    const json = JSON.stringify(caps, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `capabilities-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    message.success('已导出能力定义');
  }, [caps]);

  const handleImport = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const imported = JSON.parse(e.target?.result as string);
        if (Array.isArray(imported)) {
          const merged = [...imported, ...caps.filter(c => !imported.some((i: any) => i.id === c.id))];
          setCaps(merged);
          saveToStorage(merged);
          message.success(`已导入 ${imported.length} 个能力`);
        }
      } catch {
        message.error('导入失败：文件格式错误');
      }
    };
    reader.readAsText(file);
    return false;
  }, [caps, saveToStorage]);

  const filtered = useMemo(() => {
    let result = caps;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(c =>
        c.name.toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q)
      );
    }
    if (filterSource) {
      result = result.filter(c => c.source === filterSource);
    }
    return result;
  }, [caps, search, filterSource]);

  const columns: ColumnsType<CapabilityDef> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'source',
      key: 'source',
      width: 120,
      render: (source: CapabilitySource) => {
        const cfg = SOURCE_CONFIG[source];
        return <Tag color={cfg.color} icon={cfg.icon}>{cfg.label}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (v: number) => new Date(v * 1000).toLocaleString(),
    },
    { title: '关联 Agent', dataIndex: 'agent_count', key: 'agent_count', width: 100 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_, r: CapabilityDef) => (
        <Space size="small">
          <Tooltip title="编辑">
            <Button size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(r)} />
          </Tooltip>
          <Tooltip title="导出">
            <Button size="small" icon={<ExportOutlined />} onClick={() => {
              const json = JSON.stringify(r, null, 2);
              const blob = new Blob([json], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `${r.name}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }} />
          </Tooltip>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(r.id)}>
            <Tooltip title="删除">
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      {/* Toolbar */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
            新建能力
          </Button>
          <Button icon={<DownloadOutlined />} onClick={handleExport}>
            导出全部
          </Button>
          <Upload beforeUpload={handleImport} showUploadList={false} accept=".json">
            <Button icon={<ImportOutlined />}>导入</Button>
          </Upload>
        </Space>
        <Space>
          <Select
            placeholder="所有类型"
            value={filterSource}
            onChange={setFilterSource}
            allowClear
            style={{ width: 120 }}
            options={Object.entries(SOURCE_CONFIG).map(([k, v]) => ({ label: v.label, value: k }))}
          />
          <Input
            placeholder="搜索能力..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={e => setSearch(e.target.value)}
            allowClear
            style={{ width: 260 }}
          />
        </Space>
      </div>

      {/* Stats */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic title="能力总数" value={caps.length} prefix={<ApiOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="外部服务" value={caps.filter(c => c.source === 'external_service').length} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="系统预置" value={caps.filter(c => c.source === 'preset').length} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="在线编写" value={caps.filter(c => c.source === 'online_edit').length} />
          </Card>
        </Col>
      </Row>

      <Table<CapabilityDef>
        columns={columns}
        dataSource={filtered}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10, showTotal: t => `共 ${t} 项能力` }}
        size="middle"
      />

      {/* Create/Edit Modal */}
      <Modal
        title={editingCap ? '编辑能力' : '新建能力'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        width={700}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="能力名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="能力描述" />
          </Form.Item>
          <Form.Item name="source" label="类型" rules={[{ required: true }]}>
            <Select options={Object.entries(SOURCE_CONFIG).map(([k, v]) => ({ label: v.label, value: k }))} />
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prev, curr) => prev.source !== curr.source}>
            {({ getFieldValue }) => {
              const source = getFieldValue('source');
              if (source === 'external_service') {
                return (
                  <>
                    <Divider>外部服务配置</Divider>
                    <Form.Item name="url" label="URL" rules={[{ required: true }]}>
                      <Input placeholder="https://api.example.com/endpoint" />
                    </Form.Item>
                    <Form.Item name="method" label="HTTP 方法">
                      <Select options={[
                        { label: 'GET', value: 'GET' },
                        { label: 'POST', value: 'POST' },
                        { label: 'PUT', value: 'PUT' },
                        { label: 'DELETE', value: 'DELETE' },
                      ]} />
                    </Form.Item>
                    <Form.Item name="headers" label="请求头（每行 key: value）">
                      <TextArea rows={3} placeholder={"Authorization: Bearer xxx\nContent-Type: application/json"} />
                    </Form.Item>
                    <Form.Item name="body" label="请求体">
                      <TextArea rows={3} placeholder='{"key": "value"}' />
                    </Form.Item>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name="output_mapping" label="输出映射">
                          <Input placeholder="$.data" />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name="blackboard_key" label="存储键">
                          <Input placeholder="result" />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item name="timeout" label="超时（秒）">
                      <Input type="number" min={1} max={60} />
                    </Form.Item>
                  </>
                );
              }
              if (source === 'online_edit') {
                return (
                  <>
                    <Divider>代码编写</Divider>
                    <Form.Item name="code" label="代码" rules={[{ required: true }]}>
                      <TextArea rows={10} placeholder="// 输入能力代码" style={{ fontFamily: 'monospace' }} />
                    </Form.Item>
                  </>
                );
              }
              return null;
            }}
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

// ======================== Main Page ========================

export default function CapabilityMarketPage() {
  const items = [
    {
      key: 'marketplace',
      label: <Space><ShopOutlined />插件市场</Space>,
      children: <MarketplaceTab />,
    },
    {
      key: 'my_capabilities',
      label: <Space><ApiOutlined />我的能力</Space>,
      children: <MyCapabilitiesTab />,
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h3 style={{ margin: '0 0 16px' }}>能力市场</h3>
      <Tabs items={items} defaultActiveKey="marketplace" />
    </div>
  );
}