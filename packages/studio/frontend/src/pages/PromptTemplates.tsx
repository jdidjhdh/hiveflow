import { useState, useCallback, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, Popconfirm,
  message, Typography, Divider, Badge, Tooltip, Empty, List, Drawer, Descriptions,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, HistoryOutlined,
  RollbackOutlined, ExperimentOutlined, CopyOutlined, SearchOutlined,
  DiffOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { apiFetch, getErrorMessage } from '@/api';
import PageMaturityNotice from '@/components/PageMaturityNotice';
import { useI18n } from '@/i18n';

const { Title, Text } = Typography;
const { TextArea } = Input;

// ======================== Types ========================

interface TemplateItem {
  id: string;
  name: string;
  category: string;
  description: string;
  tags: string[];
  variables: string[];
  model_hints: string[];
  current_version: number;
  total_versions: number;
  created_at: number;
  updated_at: number;
}

interface TemplateDetail {
  id: string;
  name: string;
  content: string;
  category: string;
  description: string;
  tags: string[];
  variables: string[];
  model_hints: string[];
  current_version: number;
  requested_version: number;
  created_at: number;
  updated_at: number;
}

interface VersionInfo {
  version: number;
  created_at: number;
  created_by: string;
  change_summary: string;
  content_length: number;
}

interface TestResult {
  template_id: string;
  version: number;
  original: string;
  rendered: string;
  variables_used: string[];
  unreplaced_variables: string[];
  character_count: number;
  token_estimate: number;
}

interface CompareResult {
  template_id: string;
  version_a: number;
  version_b: number;
  diff: string[];
  added_lines: number;
  removed_lines: number;
  similarity: number;
}

// ======================== Category Config ========================

const categoryColors: Record<string, string> = {
  general: 'blue',
  chat: 'green',
  rag: 'orange',
  agent: 'purple',
  tool: 'cyan',
};

const categoryKeys = ['general', 'chat', 'rag', 'agent', 'tool'] as const;

// ======================== Main Component ========================

export default function PromptTemplatesPage() {
  const { t } = useI18n();
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateDetail | null>(null);
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<TemplateItem | null>(null);
  const [versionDrawerOpen, setVersionDrawerOpen] = useState(false);
  const [testDrawerOpen, setTestDrawerOpen] = useState(false);
  const [compareDrawerOpen, setCompareDrawerOpen] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [searchText, setSearchText] = useState('');
  const [filterCategory, setFilterCategory] = useState<string | undefined>();
  const [form] = Form.useForm();
  const [testForm] = Form.useForm();
  const [compareForm] = Form.useForm();

  // ======================== Fetch Templates ========================

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterCategory) params.set('category', filterCategory);
      if (searchText) params.set('q', searchText);
      const data = await apiFetch(`/api/prompt-templates?${params}`);
      setTemplates(data.templates || []);
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [searchText, filterCategory]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  // ======================== CRUD Operations ========================

  const handleOpenModal = useCallback((template?: TemplateItem) => {
    if (template) {
      setEditingTemplate(template);
      form.setFieldsValue({
        name: template.name,
        content: '',  // Need to fetch full content
        category: template.category,
        description: template.description,
        tags: template.tags.join(', '),
        variables: template.variables.join(', '),
        model_hints: template.model_hints.join(', '),
      });
      // Fetch full content for editing
      apiFetch(`/api/prompt-templates/${template.id}`).then((data) => {
        form.setFieldValue('content', data.content);
      });
    } else {
      setEditingTemplate(null);
      form.resetFields();
    }
    setModalOpen(true);
  }, [form]);

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const body = {
        name: values.name,
        content: values.content,
        category: values.category || 'general',
        description: values.description || '',
        tags: (values.tags || '').split(',').map((t: string) => t.trim()).filter(Boolean),
        variables: (values.variables || '').split(',').map((v: string) => v.trim()).filter(Boolean),
        model_hints: (values.model_hints || '').split(',').map((m: string) => m.trim()).filter(Boolean),
      };

      if (editingTemplate) {
        await apiFetch(`/api/prompt-templates/${editingTemplate.id}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
        message.success(t('pages.promptTemplates.messages.updated', { version: editingTemplate.current_version + 1 }));
      } else {
        await apiFetch('/api/prompt-templates', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        message.success(t('pages.promptTemplates.messages.created'));
      }
      setModalOpen(false);
      fetchTemplates();
    } catch (err: unknown) {
      if (err instanceof Error && err.message !== 'validateFields') {
        message.error(getErrorMessage(err));
      }
    }
  }, [form, editingTemplate, fetchTemplates, t]);

  const handleDelete = useCallback(async (template: TemplateItem) => {
    try {
      await apiFetch(`/api/prompt-templates/${template.id}`, { method: 'DELETE' });
      message.success(t('pages.promptTemplates.messages.deleted'));
      fetchTemplates();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [fetchTemplates, t]);

  // ======================== Version Management ========================

  const handleShowVersions = useCallback(async (template: TemplateItem) => {
    setSelectedTemplate(null);
    try {
      const [versionsData, detailData] = await Promise.all([
        apiFetch(`/api/prompt-templates/${template.id}/versions`),
        apiFetch(`/api/prompt-templates/${template.id}`),
      ]);
      setVersions(versionsData.versions || []);
      setSelectedTemplate(detailData);
      setVersionDrawerOpen(true);
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, []);

  const handleRollback = useCallback(async (version: number) => {
    if (!selectedTemplate) return;
    try {
      await apiFetch(`/api/prompt-templates/${selectedTemplate.id}/rollback/${version}`, {
        method: 'POST',
      });
      message.success(t('pages.promptTemplates.messages.rolledBack', { version }));
      setVersionDrawerOpen(false);
      fetchTemplates();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [selectedTemplate, fetchTemplates, t]);

  // ======================== Test Template ========================

  const handleTestTemplate = useCallback(async (template: TemplateItem) => {
    try {
      const detail = await apiFetch(`/api/prompt-templates/${template.id}`);
      setSelectedTemplate(detail);
      const testVars: Record<string, string> = {};
      for (const v of detail.variables || []) {
        testVars[v] = '';
      }
      testForm.setFieldsValue({ variables: testVars });
      setTestResult(null);
      setTestDrawerOpen(true);
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [testForm]);

  const handleRunTest = useCallback(async () => {
    if (!selectedTemplate) return;
    try {
      const values = await testForm.validateFields();
      const data = await apiFetch(`/api/prompt-templates/${selectedTemplate.id}/test`, {
        method: 'POST',
        body: JSON.stringify({
          template_id: selectedTemplate.id,
          variables: values.variables || {},
        }),
      });
      setTestResult(data);
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [testForm, selectedTemplate]);

  // ======================== Compare Versions ========================

  const handleCompareVersions = useCallback(async (template: TemplateItem) => {
    try {
      const versionsData = await apiFetch(`/api/prompt-templates/${template.id}/versions`);
      setVersions(versionsData.versions || []);
      setSelectedTemplate(template as unknown as TemplateDetail);
      compareForm.setFieldsValue({ version_a: 1, version_b: 2 });
      setCompareResult(null);
      setCompareDrawerOpen(true);
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [compareForm]);

  const handleRunCompare = useCallback(async () => {
    if (!selectedTemplate) return;
    try {
      const values = await compareForm.validateFields();
      const data = await apiFetch(`/api/prompt-templates/${selectedTemplate.id}/compare?version_a=${values.version_a}&version_b=${values.version_b}`, {
        method: 'POST',
      });
      setCompareResult(data);
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [compareForm, selectedTemplate]);

  // ======================== Seed Templates ========================

  const handleSeedTemplates = useCallback(async () => {
    try {
      const data = await apiFetch('/api/prompt-templates/seed', { method: 'POST' });
      message.success(t('pages.promptTemplates.messages.seeded', { count: data.seeded }));
      fetchTemplates();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [fetchTemplates, t]);

  // ======================== Copy Template ========================

  const handleCopyTemplate = useCallback(async (template: TemplateItem) => {
    try {
      const detail = await apiFetch(`/api/prompt-templates/${template.id}`);
      const body = {
        name: `${detail.name}${t('pages.promptTemplates.copySuffix')}`,
        content: detail.content,
        category: detail.category,
        description: detail.description,
        tags: detail.tags,
        variables: detail.variables,
        model_hints: detail.model_hints,
      };
      await apiFetch('/api/prompt-templates', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      message.success(t('pages.promptTemplates.messages.copied'));
      fetchTemplates();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [fetchTemplates, t]);

  // ======================== Columns ========================

  const columns: ColumnsType<TemplateItem> = [
    {
      title: t('pages.promptTemplates.columns.name'),
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string, record: TemplateItem) => (
        <Space>
          <Text strong>{name}</Text>
          <Badge count={`v${record.current_version}`} style={{ backgroundColor: '#52c41a' }} />
        </Space>
      ),
    },
    {
      title: t('pages.promptTemplates.columns.category'),
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (cat: string) => (
        <Tag color={categoryColors[cat] || 'default'}>
          {categoryKeys.includes(cat as typeof categoryKeys[number])
            ? t(`pages.promptTemplates.categories.${cat}` as 'pages.promptTemplates.categories.general')
            : cat}
        </Tag>
      ),
    },
    {
      title: t('pages.promptTemplates.columns.description'),
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: t('pages.promptTemplates.columns.tags'),
      dataIndex: 'tags',
      key: 'tags',
      width: 200,
      render: (tags: string[]) => (
        <Space wrap>
          {tags.map((tag) => <Tag key={tag}>{tag}</Tag>)}
        </Space>
      ),
    },
    {
      title: t('pages.promptTemplates.columns.variables'),
      dataIndex: 'variables',
      key: 'variables',
      width: 150,
      render: (vars: string[]) => (
        <Text type="secondary">{vars.length > 0 ? `{{${vars.join('}, {')}}}` : '-'}</Text>
      ),
    },
    {
      title: t('pages.promptTemplates.columns.version'),
      dataIndex: 'total_versions',
      key: 'total_versions',
      width: 80,
      align: 'center',
    },
    {
      title: t('pages.promptTemplates.columns.actions'),
      key: 'actions',
      width: 280,
      render: (_: unknown, record: TemplateItem) => (
        <Space>
          <Tooltip title={t('pages.promptTemplates.tooltips.edit')}>
            <Button size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)} />
          </Tooltip>
          <Tooltip title={t('pages.promptTemplates.tooltips.versions')}>
            <Button size="small" icon={<HistoryOutlined />} onClick={() => handleShowVersions(record)} />
          </Tooltip>
          <Tooltip title={t('pages.promptTemplates.tooltips.test')}>
            <Button size="small" icon={<ExperimentOutlined />} onClick={() => handleTestTemplate(record)} />
          </Tooltip>
          <Tooltip title={t('pages.promptTemplates.tooltips.compare')}>
            <Button size="small" icon={<DiffOutlined />} onClick={() => handleCompareVersions(record)} />
          </Tooltip>
          <Tooltip title={t('pages.promptTemplates.tooltips.copy')}>
            <Button size="small" icon={<CopyOutlined />} onClick={() => handleCopyTemplate(record)} />
          </Tooltip>
          <Popconfirm title={t('pages.promptTemplates.confirmDelete')} onConfirm={() => handleDelete(record)}>
            <Tooltip title={t('pages.promptTemplates.tooltips.delete')}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ======================== Render ========================

  return (
    <div style={{ padding: 24 }}>
      <PageMaturityNotice pageKey="promptTemplates" />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Title level={4} style={{ margin: 0 }}>{t('pages.promptTemplates.title')}</Title>
          <Text type="secondary">{t('pages.promptTemplates.subtitle')}</Text>
        </Space>
        <Space>
          <Button icon={<PlusOutlined />} type="primary" onClick={() => handleOpenModal()}>
            {t('pages.promptTemplates.create')}
          </Button>
          <Button icon={<ThunderboltOutlined />} onClick={handleSeedTemplates}>
            {t('pages.promptTemplates.seed')}
          </Button>
        </Space>
      </div>

      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder={t('pages.promptTemplates.searchPlaceholder')}
          prefix={<SearchOutlined />}
          style={{ width: 250 }}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          onPressEnter={fetchTemplates}
        />
        <Select
          placeholder={t('pages.promptTemplates.allCategories')}
          style={{ width: 150 }}
          allowClear
          value={filterCategory}
          onChange={setFilterCategory}
          options={categoryKeys.map((key) => ({
            label: t(`pages.promptTemplates.categories.${key}`),
            value: key,
          }))}
        />
      </Space>

      <Table
        columns={columns}
        dataSource={templates}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />

      {/* Create/Edit Modal */}
      <Modal
        title={editingTemplate ? t('pages.promptTemplates.modal.editTitle') : t('pages.promptTemplates.modal.createTitle')}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        width={800}
        okText={t('pages.promptTemplates.modal.save')}
        cancelText={t('pages.promptTemplates.modal.cancel')}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label={t('pages.promptTemplates.form.name')} rules={[{ required: true }]}>
            <Input placeholder={t('pages.promptTemplates.form.namePlaceholder')} />
          </Form.Item>
          <Form.Item name="category" label={t('pages.promptTemplates.form.category')} rules={[{ required: true }]}>
            <Select options={categoryKeys.map((key) => ({
              label: t(`pages.promptTemplates.categories.${key}`),
              value: key,
            }))} />
          </Form.Item>
          <Form.Item name="content" label={t('pages.promptTemplates.form.content')} rules={[{ required: true }]}>
            <TextArea rows={10} placeholder={t('pages.promptTemplates.form.contentPlaceholder')} style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="description" label={t('pages.promptTemplates.form.description')}>
            <Input placeholder={t('pages.promptTemplates.form.descriptionPlaceholder')} />
          </Form.Item>
          <Form.Item name="tags" label={t('pages.promptTemplates.form.tags')}>
            <Input placeholder={t('pages.promptTemplates.form.tagsPlaceholder')} />
          </Form.Item>
          <Form.Item name="variables" label={t('pages.promptTemplates.form.variables')}>
            <Input placeholder={t('pages.promptTemplates.form.variablesPlaceholder')} />
          </Form.Item>
          <Form.Item name="model_hints" label={t('pages.promptTemplates.form.modelHints')}>
            <Input placeholder={t('pages.promptTemplates.form.modelHintsPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Version History Drawer */}
      <Drawer
        title={t('pages.promptTemplates.versionDrawer.title', { name: selectedTemplate?.name || '' })}
        open={versionDrawerOpen}
        onClose={() => setVersionDrawerOpen(false)}
        width={600}
      >
        {versions.length === 0 ? (
          <Empty description={t('pages.promptTemplates.versionDrawer.noVersions')} />
        ) : (
          <List
            dataSource={[...versions].reverse()}
            renderItem={(v) => (
              <List.Item
                actions={[
                  <Popconfirm title={t('pages.promptTemplates.versionDrawer.confirmRollback', { version: v.version })} onConfirm={() => handleRollback(v.version)}>
                    <Button size="small" icon={<RollbackOutlined />} type="link">{t('pages.promptTemplates.versionDrawer.rollback')}</Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Tag color={v.version === selectedTemplate?.current_version ? 'green' : 'default'}>
                        v{v.version}
                      </Tag>
                      {v.version === selectedTemplate?.current_version && <Text type="success">{t('pages.promptTemplates.versionDrawer.currentVersion')}</Text>}
                    </Space>
                  }
                  description={
                    <Space direction="vertical" size={0}>
                      <Text>{v.change_summary || t('pages.promptTemplates.versionDrawer.noChangeSummary')}</Text>
                      <Text type="secondary">
                        {new Date(v.created_at * 1000).toLocaleString()} · {t('pages.promptTemplates.versionDrawer.characters', { count: v.content_length })}
                      </Text>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Drawer>

      {/* Test Drawer */}
      <Drawer
        title={t('pages.promptTemplates.testDrawer.title', { name: selectedTemplate?.name || '' })}
        open={testDrawerOpen}
        onClose={() => setTestDrawerOpen(false)}
        width={700}
      >
        <Form form={testForm} layout="vertical">
          <Text strong>{t('pages.promptTemplates.testDrawer.variableAssignment')}</Text>
          <Form.Item name="variables" style={{ marginTop: 8 }}>
            <Form.List name="variables">
              {(_fields) => (
                <Space direction="vertical" style={{ width: '100%' }}>
                  {selectedTemplate?.variables?.map((v) => (
                    <Form.Item key={v} label={`{{${v}}}`} name={[v]}>
                      <Input placeholder={t('pages.promptTemplates.testDrawer.inputValue', { name: v })} />
                    </Form.Item>
                  ))}
                </Space>
              )}
            </Form.List>
          </Form.Item>
          <Button type="primary" onClick={handleRunTest}>
            <ExperimentOutlined /> {t('pages.promptTemplates.testDrawer.runTest')}
          </Button>
        </Form>

        {testResult && (
          <div style={{ marginTop: 16 }}>
            <Divider>{t('pages.promptTemplates.testDrawer.results')}</Divider>
            <Descriptions bordered size="small" column={2}>
              <Descriptions.Item label={t('pages.promptTemplates.testDrawer.version')}>v{testResult.version}</Descriptions.Item>
              <Descriptions.Item label={t('pages.promptTemplates.testDrawer.charCount')}>{testResult.character_count}</Descriptions.Item>
              <Descriptions.Item label={t('pages.promptTemplates.testDrawer.tokenEstimate')}>{testResult.token_estimate}</Descriptions.Item>
              <Descriptions.Item label={t('pages.promptTemplates.testDrawer.unreplacedVariables')}>
                {testResult.unreplaced_variables.length > 0
                  ? testResult.unreplaced_variables.map((v) => `{{${v}}}`).join(', ')
                  : t('pages.promptTemplates.testDrawer.none')}
              </Descriptions.Item>
            </Descriptions>
            <Divider>{t('pages.promptTemplates.testDrawer.rendered')}</Divider>
            <pre style={{
              background: '#f5f5f5',
              padding: 12,
              borderRadius: 4,
              whiteSpace: 'pre-wrap',
              maxHeight: 400,
              overflow: 'auto',
              fontSize: 12,
            }}>
              {testResult.rendered}
            </pre>
          </div>
        )}
      </Drawer>

      {/* Compare Drawer */}
      <Drawer
        title={t('pages.promptTemplates.compareDrawer.title', { name: selectedTemplate?.name || '' })}
        open={compareDrawerOpen}
        onClose={() => setCompareDrawerOpen(false)}
        width={800}
      >
        <Form form={compareForm} layout="inline">
          <Form.Item name="version_a" label={t('pages.promptTemplates.compareDrawer.versionA')}>
            <Select style={{ width: 120 }}>
              {versions.map((v) => (
                <Select.Option key={v.version} value={v.version}>v{v.version}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="version_b" label={t('pages.promptTemplates.compareDrawer.versionB')}>
            <Select style={{ width: 120 }}>
              {versions.map((v) => (
                <Select.Option key={v.version} value={v.version}>v{v.version}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={handleRunCompare} icon={<DiffOutlined />}>
              {t('pages.promptTemplates.compareDrawer.compare')}
            </Button>
          </Form.Item>
        </Form>

        {compareResult && (
          <div style={{ marginTop: 16 }}>
            <Descriptions bordered size="small" column={3}>
              <Descriptions.Item label={t('pages.promptTemplates.compareDrawer.addedLines')}>{compareResult.added_lines}</Descriptions.Item>
              <Descriptions.Item label={t('pages.promptTemplates.compareDrawer.removedLines')}>{compareResult.removed_lines}</Descriptions.Item>
              <Descriptions.Item label={t('pages.promptTemplates.compareDrawer.similarity')}>
                {(compareResult.similarity * 100).toFixed(1)}%
              </Descriptions.Item>
            </Descriptions>
            <Divider>{t('pages.promptTemplates.compareDrawer.diff')}</Divider>
            <pre style={{
              background: '#1e1e1e',
              color: '#d4d4d4',
              padding: 12,
              borderRadius: 4,
              maxHeight: 500,
              overflow: 'auto',
              fontSize: 12,
              fontFamily: 'monospace',
            }}>
              {compareResult.diff.map((line, i) => {
                let color = '#d4d4d4';
                if (line.startsWith('+')) color = '#3fb950';
                else if (line.startsWith('-')) color = '#f85149';
                else if (line.startsWith('@@')) color = '#58a6ff';
                return <div key={i} style={{ color }}>{line}</div>;
              })}
            </pre>
          </div>
        )}
      </Drawer>
    </div>
  );
}
