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
import { apiFetch, getErrorMessage } from '@/utils/api';

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

// ======================== Main Component ========================

export default function PromptTemplatesPage() {
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
        message.success(`模板已更新 (v${editingTemplate.current_version + 1})`);
      } else {
        await apiFetch('/api/prompt-templates', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        message.success('模板已创建');
      }
      setModalOpen(false);
      fetchTemplates();
    } catch (err: unknown) {
      if (err instanceof Error && err.message !== 'validateFields') {
        message.error(getErrorMessage(err));
      }
    }
  }, [form, editingTemplate, fetchTemplates]);

  const handleDelete = useCallback(async (template: TemplateItem) => {
    try {
      await apiFetch(`/api/prompt-templates/${template.id}`, { method: 'DELETE' });
      message.success('模板已删除');
      fetchTemplates();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [fetchTemplates]);

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
      message.success(`已回滚到版本 ${version}`);
      setVersionDrawerOpen(false);
      fetchTemplates();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [selectedTemplate, fetchTemplates]);

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
      message.success(`已预置 ${data.seeded} 个常用模板`);
      fetchTemplates();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [fetchTemplates]);

  // ======================== Copy Template ========================

  const handleCopyTemplate = useCallback(async (template: TemplateItem) => {
    try {
      const detail = await apiFetch(`/api/prompt-templates/${template.id}`);
      const body = {
        name: `${detail.name} (副本)`,
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
      message.success('模板已复制');
      fetchTemplates();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  }, [fetchTemplates]);

  // ======================== Columns ========================

  const columns: ColumnsType<TemplateItem> = [
    {
      title: '名称',
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
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (cat: string) => <Tag color={categoryColors[cat] || 'default'}>{cat}</Tag>,
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
          {tags.map((t) => <Tag key={t}>{t}</Tag>)}
        </Space>
      ),
    },
    {
      title: '变量',
      dataIndex: 'variables',
      key: 'variables',
      width: 150,
      render: (vars: string[]) => (
        <Text type="secondary">{vars.length > 0 ? `{{${vars.join('}, {')}}}` : '-'}</Text>
      ),
    },
    {
      title: '版本',
      dataIndex: 'total_versions',
      key: 'total_versions',
      width: 80,
      align: 'center',
    },
    {
      title: '操作',
      key: 'actions',
      width: 280,
      render: (_: unknown, record: TemplateItem) => (
        <Space>
          <Tooltip title="编辑">
            <Button size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)} />
          </Tooltip>
          <Tooltip title="版本历史">
            <Button size="small" icon={<HistoryOutlined />} onClick={() => handleShowVersions(record)} />
          </Tooltip>
          <Tooltip title="测试模板">
            <Button size="small" icon={<ExperimentOutlined />} onClick={() => handleTestTemplate(record)} />
          </Tooltip>
          <Tooltip title="版本对比">
            <Button size="small" icon={<DiffOutlined />} onClick={() => handleCompareVersions(record)} />
          </Tooltip>
          <Tooltip title="复制">
            <Button size="small" icon={<CopyOutlined />} onClick={() => handleCopyTemplate(record)} />
          </Tooltip>
          <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record)}>
            <Tooltip title="删除">
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
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Title level={4} style={{ margin: 0 }}>Prompt 模板库</Title>
          <Text type="secondary">管理和版本控制您的 Prompt 模板</Text>
        </Space>
        <Space>
          <Button icon={<PlusOutlined />} type="primary" onClick={() => handleOpenModal()}>
            新建模板
          </Button>
          <Button icon={<ThunderboltOutlined />} onClick={handleSeedTemplates}>
            预置模板
          </Button>
        </Space>
      </div>

      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索模板..."
          prefix={<SearchOutlined />}
          style={{ width: 250 }}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          onPressEnter={fetchTemplates}
        />
        <Select
          placeholder="所有分类"
          style={{ width: 150 }}
          allowClear
          value={filterCategory}
          onChange={setFilterCategory}
          options={Object.entries(categoryColors).map(([key, _]) => ({ label: key, value: key }))}
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
        title={editingTemplate ? '编辑模板' : '新建模板'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        width={800}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="模板名称" />
          </Form.Item>
          <Form.Item name="category" label="分类" rules={[{ required: true }]}>
            <Select options={[
              { label: '通用', value: 'general' },
              { label: '对话', value: 'chat' },
              { label: 'RAG', value: 'rag' },
              { label: 'Agent', value: 'agent' },
              { label: '工具', value: 'tool' },
            ]} />
          </Form.Item>
          <Form.Item name="content" label="模板内容" rules={[{ required: true }]}>
            <TextArea rows={10} placeholder={"使用 {{variable_name}} 定义变量"} style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="模板描述" />
          </Form.Item>
          <Form.Item name="tags" label="标签（逗号分隔）">
            <Input placeholder="assistant, chat, qa" />
          </Form.Item>
          <Form.Item name="variables" label="变量列表（逗号分隔）">
            <Input placeholder="user_input, context, question" />
          </Form.Item>
          <Form.Item name="model_hints" label="推荐模型（逗号分隔）">
            <Input placeholder="gpt-4o, claude-3-sonnet" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Version History Drawer */}
      <Drawer
        title={`版本历史 - ${selectedTemplate?.name || ''}`}
        open={versionDrawerOpen}
        onClose={() => setVersionDrawerOpen(false)}
        width={600}
      >
        {versions.length === 0 ? (
          <Empty description="暂无版本记录" />
        ) : (
          <List
            dataSource={[...versions].reverse()}
            renderItem={(v) => (
              <List.Item
                actions={[
                  <Popconfirm title={`确认回滚到 v${v.version}?`} onConfirm={() => handleRollback(v.version)}>
                    <Button size="small" icon={<RollbackOutlined />} type="link">回滚</Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Tag color={v.version === selectedTemplate?.current_version ? 'green' : 'default'}>
                        v{v.version}
                      </Tag>
                      {v.version === selectedTemplate?.current_version && <Text type="success">当前版本</Text>}
                    </Space>
                  }
                  description={
                    <Space direction="vertical" size={0}>
                      <Text>{v.change_summary || '无变更说明'}</Text>
                      <Text type="secondary">
                        {new Date(v.created_at * 1000).toLocaleString()} · {v.content_length} 字符
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
        title={`测试模板 - ${selectedTemplate?.name || ''}`}
        open={testDrawerOpen}
        onClose={() => setTestDrawerOpen(false)}
        width={700}
      >
        <Form form={testForm} layout="vertical">
          <Text strong>变量赋值：</Text>
          <Form.Item name="variables" style={{ marginTop: 8 }}>
            <Form.List name="variables">
              {(_fields) => (
                <Space direction="vertical" style={{ width: '100%' }}>
                  {selectedTemplate?.variables?.map((v) => (
                    <Form.Item key={v} label={`{{${v}}}`} name={[v]}>
                      <Input placeholder={`输入 ${v} 的值`} />
                    </Form.Item>
                  ))}
                </Space>
              )}
            </Form.List>
          </Form.Item>
          <Button type="primary" onClick={handleRunTest}>
            <ExperimentOutlined /> 运行测试
          </Button>
        </Form>

        {testResult && (
          <div style={{ marginTop: 16 }}>
            <Divider>测试结果</Divider>
            <Descriptions bordered size="small" column={2}>
              <Descriptions.Item label="版本">v{testResult.version}</Descriptions.Item>
              <Descriptions.Item label="字符数">{testResult.character_count}</Descriptions.Item>
              <Descriptions.Item label="Token 估算">{testResult.token_estimate}</Descriptions.Item>
              <Descriptions.Item label="未替换变量">
                {testResult.unreplaced_variables.length > 0
                  ? testResult.unreplaced_variables.map((v) => `{{${v}}}`).join(', ')
                  : '无'}
              </Descriptions.Item>
            </Descriptions>
            <Divider>渲染结果</Divider>
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
        title={`版本对比 - ${selectedTemplate?.name || ''}`}
        open={compareDrawerOpen}
        onClose={() => setCompareDrawerOpen(false)}
        width={800}
      >
        <Form form={compareForm} layout="inline">
          <Form.Item name="version_a" label="版本 A">
            <Select style={{ width: 120 }}>
              {versions.map((v) => (
                <Select.Option key={v.version} value={v.version}>v{v.version}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="version_b" label="版本 B">
            <Select style={{ width: 120 }}>
              {versions.map((v) => (
                <Select.Option key={v.version} value={v.version}>v{v.version}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={handleRunCompare} icon={<DiffOutlined />}>
              对比
            </Button>
          </Form.Item>
        </Form>

        {compareResult && (
          <div style={{ marginTop: 16 }}>
            <Descriptions bordered size="small" column={3}>
              <Descriptions.Item label="新增行">{compareResult.added_lines}</Descriptions.Item>
              <Descriptions.Item label="删除行">{compareResult.removed_lines}</Descriptions.Item>
              <Descriptions.Item label="相似度">
                {(compareResult.similarity * 100).toFixed(1)}%
              </Descriptions.Item>
            </Descriptions>
            <Divider>差异对比</Divider>
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
