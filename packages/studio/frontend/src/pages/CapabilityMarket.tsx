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

  Select, Tabs, Card, Statistic, Row, Col, Tooltip, Typography, Upload, Divider,

} from 'antd';

import type { ColumnsType } from 'antd/es/table';

import {

  SearchOutlined, ApiOutlined, CodeOutlined,

  CloudServerOutlined, UploadOutlined, DeleteOutlined, EditOutlined, PlusOutlined, DownloadOutlined, ShopOutlined, CheckCircleOutlined,

  ExportOutlined, ImportOutlined,

} from '@ant-design/icons';

import type { CapabilityDef, CapabilitySource } from '@/types';

import { apiFetch, getErrorMessage } from '@/api';

import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';

import { useEngineStore } from '@/store/useEngineStore';

import { DemoDataBanner } from '@/components/RealModeRequired';

import {

  MOCK_MARKETPLACE_CATEGORIES,

  MOCK_MARKETPLACE_PLUGINS,

  mockMarketplaceStats,

} from '@/data/mockMarketplace';

import { useI18n } from '@/i18n';



const { Text } = Typography;

const { TextArea } = Input;



const SOURCE_STYLE: Record<CapabilitySource, { color: string; icon: React.ReactNode }> = {

  preset:            { color: 'blue',   icon: <CloudServerOutlined /> },

  external_service:  { color: 'green',  icon: <ApiOutlined /> },

  upload:            { color: 'orange', icon: <UploadOutlined /> },

  online_edit:       { color: 'purple', icon: <CodeOutlined /> },

};



const SOURCE_I18N_KEY: Record<CapabilitySource, 'pages.capabilityMarket.myCapabilities.source.preset' | 'pages.capabilityMarket.myCapabilities.source.externalService' | 'pages.capabilityMarket.myCapabilities.source.upload' | 'pages.capabilityMarket.myCapabilities.source.onlineEdit'> = {

  preset: 'pages.capabilityMarket.myCapabilities.source.preset',

  external_service: 'pages.capabilityMarket.myCapabilities.source.externalService',

  upload: 'pages.capabilityMarket.myCapabilities.source.upload',

  online_edit: 'pages.capabilityMarket.myCapabilities.source.onlineEdit',

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

  const { t } = useI18n();

  const { message } = App.useApp();

  const engineMode = useEngineStore((s) => s.mode);

  const runtimeMode = useAgentRuntimeStore(s => s.runtimeMode);

  const fetchRuntime = useAgentRuntimeStore(s => s.fetchRuntime);

  const [plugins, setPlugins] = useState<PluginMarketplaceItem[]>([]);

  const [loading, setLoading] = useState(false);

  const [categories, setCategories] = useState<Record<string, string>>({});

  const [selectedCategory, setSelectedCategory] = useState<string>();

  const [searchText, setSearchText] = useState('');

  const [stats, setStats] = useState<MarketplaceStats | null>(null);



  const fetchMarketplace = useCallback(async () => {

    setLoading(true);

    try {

      if (engineMode === 'mock') {

        let list = [...MOCK_MARKETPLACE_PLUGINS];

        if (selectedCategory) {

          list = list.filter((p) => p.category === selectedCategory);

        }

        if (searchText) {

          const q = searchText.toLowerCase();

          list = list.filter(

            (p) =>

              p.name.toLowerCase().includes(q)

              || p.description.toLowerCase().includes(q)

              || p.tags.some((t) => t.toLowerCase().includes(q)),

          );

        }

        setPlugins(list);

        setStats(mockMarketplaceStats(list));

        return;

      }

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

  }, [engineMode, selectedCategory, searchText, message]);



  const fetchCategories = useCallback(async () => {

    if (engineMode === 'mock') {

      setCategories(MOCK_MARKETPLACE_CATEGORIES);

      return;

    }

    try {

      const data = await apiFetch('/api/plugins/marketplace/categories');

      setCategories(data.categories || {});

    } catch {

      // Ignore if not available

    }

  }, [engineMode]);



  useEffect(() => {

    fetchMarketplace();

    fetchCategories();

    fetchRuntime();

  }, [fetchMarketplace, fetchCategories, fetchRuntime]);



  const handleInstall = useCallback(async (plugin: PluginMarketplaceItem) => {

    if (engineMode === 'mock') {

      message.warning(t('pages.capabilityMarket.marketplace.messages.mockInstallWarning'));

      return;

    }

    try {

      const data = await apiFetch('/api/plugins/install', {

        method: 'POST',

        body: JSON.stringify({ plugin_id: plugin.plugin_id }),

      });

      const skills: string[] = data.registered_skills || [];

      if (skills.length > 0) {

        message.success(

          t('pages.capabilityMarket.marketplace.messages.installedWithSkills', { name: plugin.name, count: skills.length }),

          5,

        );

        Modal.info({

          title: t('pages.capabilityMarket.marketplace.skillModal.title'),

          content: (

            <div>

              <p>{t('pages.capabilityMarket.marketplace.skillModal.description')}</p>

              <ul style={{ marginTop: 8, paddingLeft: 20 }}>

                {skills.map(s => (

                  <li key={s}><Text code>{s}</Text></li>

                ))}

              </ul>

            </div>

          ),

        });

      } else {

        message.success(t('pages.capabilityMarket.marketplace.messages.installed', { name: plugin.name }));

        if (runtimeMode !== 'agent') {

          message.info(t('pages.capabilityMarket.marketplace.messages.enableAgentMode'), 6);

        } else {

          message.warning(t('pages.capabilityMarket.marketplace.messages.noSkillsRegistered'), 5);

        }

      }

      fetchMarketplace();

      fetchRuntime();

    } catch (err) {

      message.error(getErrorMessage(err));

    }

  }, [engineMode, fetchMarketplace, fetchRuntime, runtimeMode, message, t]);



  const columns: ColumnsType<PluginMarketplaceItem> = [

    {

      title: t('pages.capabilityMarket.marketplace.columns.name'),

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

      title: t('pages.capabilityMarket.marketplace.columns.category'),

      dataIndex: 'category',

      key: 'category',

      width: 120,

      render: (cat: string) => <Tag color="blue">{categories[cat] || cat}</Tag>,

    },

    {

      title: t('pages.capabilityMarket.marketplace.columns.description'),

      dataIndex: 'description',

      key: 'description',

      ellipsis: true,

    },

    {

      title: t('pages.capabilityMarket.marketplace.columns.tags'),

      dataIndex: 'tags',

      key: 'tags',

      width: 200,

      render: (tags: string[]) => (

        <Space wrap>

          {tags.slice(0, 3).map((tag) => <Tag key={tag}>{tag}</Tag>)}

          {tags.length > 3 && <Tag>+{tags.length - 3}</Tag>}

        </Space>

      ),

    },

    {

      title: t('pages.capabilityMarket.marketplace.columns.status'),

      key: 'status',

      width: 100,

      render: (_, record: PluginMarketplaceItem) => (

        record.status === 'installed'

          ? <Tag color="green" icon={<CheckCircleOutlined />}>{t('pages.capabilityMarket.marketplace.status.installed')}</Tag>

          : <Tag color="default">{t('pages.capabilityMarket.marketplace.status.notInstalled')}</Tag>

      ),

    },

    {

      title: t('pages.capabilityMarket.marketplace.columns.actions'),

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

              {t('pages.capabilityMarket.marketplace.install')}

            </Button>

          )}

        </Space>

      ),

    },

  ];



  return (

    <div>

      <DemoDataBanner message={t('pages.capabilityMarket.marketplace.demoBanner')} />

      {/* Stats */}

      {stats && (

        <Row gutter={16} style={{ marginBottom: 16 }}>

          <Col span={6}>

            <Card>

              <Statistic title={t('pages.capabilityMarket.marketplace.totalPlugins')} value={stats.total} prefix={<ShopOutlined />} />

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

          placeholder={t('pages.capabilityMarket.marketplace.searchPlaceholder')}

          prefix={<SearchOutlined />}

          value={searchText}

          onChange={(e) => setSearchText(e.target.value)}

          onPressEnter={fetchMarketplace}

          allowClear

          style={{ width: 250 }}

        />

        <Select

          placeholder={t('pages.capabilityMarket.marketplace.allCategories')}

          value={selectedCategory}

          onChange={setSelectedCategory}

          allowClear

          style={{ width: 150 }}

          options={Object.entries(categories).map(([k, v]) => ({ label: v, value: k }))}

        />

        <Button onClick={fetchMarketplace}>{t('pages.capabilityMarket.marketplace.refresh')}</Button>

      </Space>



      <Table

        columns={columns}

        dataSource={plugins}

        rowKey="plugin_id"

        loading={loading}

        pagination={{ pageSize: 10, showTotal: (total) => t('pages.capabilityMarket.marketplace.totalCount', { count: total }) }}

      />

    </div>

  );

}



// ======================== My Capabilities Tab ========================



function MyCapabilitiesTab() {

  const { t } = useI18n();

  const { message } = App.useApp();

  const [caps, setCaps] = useState<CapabilityDef[]>([]);

  const [loading, setLoading] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);

  const [editingCap, setEditingCap] = useState<CapabilityDef | null>(null);

  const [form] = Form.useForm();

  const [search, setSearch] = useState('');

  const [filterSource, setFilterSource] = useState<CapabilitySource | undefined>();



  const sourceOptions = useMemo(

    () => Object.entries(SOURCE_STYLE).map(([k]) => ({

      label: t(SOURCE_I18N_KEY[k as CapabilitySource]),

      value: k,

    })),

    [t],

  );



  const fetchCaps = useCallback(async () => {

    setLoading(true);

    try {

      // Try to fetch from backend, fallback to localStorage

      const data = await apiFetch('/api/capabilities');

      setCaps(data.capabilities || []);

    } catch {

      try {

        const stored = localStorage.getItem('hf_capabilities');

        if (stored) setCaps(JSON.parse(stored));

      } catch {

        setCaps([]);

      }

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

      message.success(editingCap ? t('pages.capabilityMarket.myCapabilities.messages.updated') : t('pages.capabilityMarket.myCapabilities.messages.created'));

    } catch (err: unknown) {

      if (err instanceof Error && err.message !== 'validateFields') {

        message.error(getErrorMessage(err));

      }

    }

  }, [form, editingCap, caps, saveToStorage, message, t]);



  const handleDelete = useCallback((id: string) => {

    const updated = caps.filter(c => c.id !== id);

    setCaps(updated);

    saveToStorage(updated);

    message.success(t('pages.capabilityMarket.myCapabilities.messages.deleted'));

  }, [caps, saveToStorage, message, t]);



  const handleExport = useCallback(() => {

    const json = JSON.stringify(caps, null, 2);

    const blob = new Blob([json], { type: 'application/json' });

    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');

    a.href = url;

    a.download = `capabilities-${Date.now()}.json`;

    a.click();

    URL.revokeObjectURL(url);

    message.success(t('pages.capabilityMarket.myCapabilities.messages.exported'));

  }, [caps, message, t]);



  const handleImport = useCallback((file: File) => {

    const reader = new FileReader();

    reader.onload = (e) => {

      try {

        const imported = JSON.parse(e.target?.result as string);

        if (Array.isArray(imported)) {

          const merged = [...imported, ...caps.filter(c => !imported.some((i: any) => i.id === c.id))];

          setCaps(merged);

          saveToStorage(merged);

          message.success(t('pages.capabilityMarket.myCapabilities.messages.imported', { count: imported.length }));

        }

      } catch {

        message.error(t('pages.capabilityMarket.myCapabilities.messages.importFailed'));

      }

    };

    reader.readAsText(file);

    return false;

  }, [caps, saveToStorage, message, t]);



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

      title: t('pages.capabilityMarket.myCapabilities.columns.name'),

      dataIndex: 'name',

      key: 'name',

      width: 200,

      ellipsis: true,

    },

    {

      title: t('pages.capabilityMarket.myCapabilities.columns.type'),

      dataIndex: 'source',

      key: 'source',

      width: 120,

      render: (source: CapabilitySource) => {

        const style = SOURCE_STYLE[source];

        return <Tag color={style.color} icon={style.icon}>{t(SOURCE_I18N_KEY[source])}</Tag>;

      },

    },

    {

      title: t('pages.capabilityMarket.myCapabilities.columns.createdAt'),

      dataIndex: 'created_at',

      key: 'created_at',

      width: 160,

      render: (v: number) => new Date(v * 1000).toLocaleString(),

    },

    { title: t('pages.capabilityMarket.myCapabilities.columns.agentCount'), dataIndex: 'agent_count', key: 'agent_count', width: 100 },

    { title: t('pages.capabilityMarket.myCapabilities.columns.description'), dataIndex: 'description', key: 'description', ellipsis: true },

    {

      title: t('pages.capabilityMarket.myCapabilities.columns.actions'),

      key: 'actions',

      width: 200,

      render: (_, r: CapabilityDef) => (

        <Space size="small">

          <Tooltip title={t('pages.capabilityMarket.myCapabilities.actions.edit')}>

            <Button size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(r)} />

          </Tooltip>

          <Tooltip title={t('pages.capabilityMarket.myCapabilities.actions.export')}>

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

          <Popconfirm title={t('pages.capabilityMarket.myCapabilities.confirmDelete')} onConfirm={() => handleDelete(r.id)}>

            <Tooltip title={t('pages.capabilityMarket.myCapabilities.actions.delete')}>

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

            {t('pages.capabilityMarket.myCapabilities.create')}

          </Button>

          <Button icon={<DownloadOutlined />} onClick={handleExport}>

            {t('pages.capabilityMarket.myCapabilities.exportAll')}

          </Button>

          <Upload beforeUpload={handleImport} showUploadList={false} accept=".json">

            <Button icon={<ImportOutlined />}>{t('pages.capabilityMarket.myCapabilities.import')}</Button>

          </Upload>

        </Space>

        <Space>

          <Select

            placeholder={t('pages.capabilityMarket.myCapabilities.allTypes')}

            value={filterSource}

            onChange={setFilterSource}

            allowClear

            style={{ width: 120 }}

            options={sourceOptions}

          />

          <Input

            placeholder={t('pages.capabilityMarket.myCapabilities.searchPlaceholder')}

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

            <Statistic title={t('pages.capabilityMarket.myCapabilities.stats.total')} value={caps.length} prefix={<ApiOutlined />} />

          </Card>

        </Col>

        <Col span={6}>

          <Card>

            <Statistic title={t('pages.capabilityMarket.myCapabilities.stats.externalService')} value={caps.filter(c => c.source === 'external_service').length} />

          </Card>

        </Col>

        <Col span={6}>

          <Card>

            <Statistic title={t('pages.capabilityMarket.myCapabilities.stats.preset')} value={caps.filter(c => c.source === 'preset').length} />

          </Card>

        </Col>

        <Col span={6}>

          <Card>

            <Statistic title={t('pages.capabilityMarket.myCapabilities.stats.onlineEdit')} value={caps.filter(c => c.source === 'online_edit').length} />

          </Card>

        </Col>

      </Row>



      <Table<CapabilityDef>

        columns={columns}

        dataSource={filtered}

        rowKey="id"

        loading={loading}

        pagination={{ pageSize: 10, showTotal: (total) => t('pages.capabilityMarket.myCapabilities.totalCount', { count: total }) }}

        size="middle"

      />



      {/* Create/Edit Modal */}

      <Modal

        title={editingCap ? t('pages.capabilityMarket.myCapabilities.modal.editTitle') : t('pages.capabilityMarket.myCapabilities.modal.createTitle')}

        open={modalOpen}

        onOk={handleSave}

        onCancel={() => setModalOpen(false)}

        width={700}

        okText={t('pages.capabilityMarket.myCapabilities.modal.save')}

        cancelText={t('pages.capabilityMarket.myCapabilities.modal.cancel')}

      >

        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>

          <Form.Item name="name" label={t('pages.capabilityMarket.myCapabilities.form.name')} rules={[{ required: true }]}>

            <Input placeholder={t('pages.capabilityMarket.myCapabilities.form.namePlaceholder')} />

          </Form.Item>

          <Form.Item name="description" label={t('pages.capabilityMarket.myCapabilities.form.description')}>

            <Input placeholder={t('pages.capabilityMarket.myCapabilities.form.descriptionPlaceholder')} />

          </Form.Item>

          <Form.Item name="source" label={t('pages.capabilityMarket.myCapabilities.form.type')} rules={[{ required: true }]}>

            <Select options={sourceOptions} />

          </Form.Item>



          <Form.Item noStyle shouldUpdate={(prev, curr) => prev.source !== curr.source}>

            {({ getFieldValue }) => {

              const source = getFieldValue('source');

              if (source === 'external_service') {

                return (

                  <>

                    <Divider>{t('pages.capabilityMarket.myCapabilities.form.externalConfig')}</Divider>

                    <Form.Item name="url" label={t('pages.capabilityMarket.myCapabilities.form.url')} rules={[{ required: true }]}>

                      <Input placeholder={t('pages.capabilityMarket.myCapabilities.form.urlPlaceholder')} />

                    </Form.Item>

                    <Form.Item name="method" label={t('pages.capabilityMarket.myCapabilities.form.method')}>

                      <Select options={[

                        { label: 'GET', value: 'GET' },

                        { label: 'POST', value: 'POST' },

                        { label: 'PUT', value: 'PUT' },

                        { label: 'DELETE', value: 'DELETE' },

                      ]} />

                    </Form.Item>

                    <Form.Item name="headers" label={t('pages.capabilityMarket.myCapabilities.form.headers')}>

                      <TextArea rows={3} placeholder={t('pages.capabilityMarket.myCapabilities.form.headersPlaceholder')} />

                    </Form.Item>

                    <Form.Item name="body" label={t('pages.capabilityMarket.myCapabilities.form.body')}>

                      <TextArea rows={3} placeholder={t('pages.capabilityMarket.myCapabilities.form.bodyPlaceholder')} />

                    </Form.Item>

                    <Row gutter={16}>

                      <Col span={12}>

                        <Form.Item name="output_mapping" label={t('pages.capabilityMarket.myCapabilities.form.outputMapping')}>

                          <Input placeholder="$.data" />

                        </Form.Item>

                      </Col>

                      <Col span={12}>

                        <Form.Item name="blackboard_key" label={t('pages.capabilityMarket.myCapabilities.form.storageKey')}>

                          <Input placeholder="result" />

                        </Form.Item>

                      </Col>

                    </Row>

                    <Form.Item name="timeout" label={t('pages.capabilityMarket.myCapabilities.form.timeout')}>

                      <Input type="number" min={1} max={60} />

                    </Form.Item>

                  </>

                );

              }

              if (source === 'online_edit') {

                return (

                  <>

                    <Divider>{t('pages.capabilityMarket.myCapabilities.form.codeEditor')}</Divider>

                    <Form.Item name="code" label={t('pages.capabilityMarket.myCapabilities.form.code')} rules={[{ required: true }]}>

                      <TextArea rows={10} placeholder={t('pages.capabilityMarket.myCapabilities.form.codePlaceholder')} style={{ fontFamily: 'monospace' }} />

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

  const { t } = useI18n();



  const items = [

    {

      key: 'marketplace',

      label: <Space><ShopOutlined />{t('pages.capabilityMarket.tabs.marketplace')}</Space>,

      children: <MarketplaceTab />,

    },

    {

      key: 'my_capabilities',

      label: <Space><ApiOutlined />{t('pages.capabilityMarket.tabs.myCapabilities')}</Space>,

      children: <MyCapabilitiesTab />,

    },

  ];



  return (

    <div style={{ padding: 24 }}>

      <h3 style={{ margin: '0 0 16px' }}>{t('pages.capabilityMarket.title')}</h3>

      <Tabs items={items} defaultActiveKey="marketplace" />

    </div>

  );

}


