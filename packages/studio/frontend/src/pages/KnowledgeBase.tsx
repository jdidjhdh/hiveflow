import { useState, useEffect } from 'react';
import {
  Card, Row, Col, Button, Input, Modal, Form, Select,
  Upload, Table, Tag, Space, Popconfirm, message, Empty, Divider, Tabs, Alert,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, SearchOutlined,
  UploadOutlined, FileTextOutlined, PlayCircleOutlined, DatabaseOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { KnowledgeBase, DocumentDef } from '@/types';
import { useKnowledgeBaseStore } from '@/store/useKnowledgeBaseStore';
import { useEngineStore } from '@/store/useEngineStore';
import PageMaturityNotice from '@/components/PageMaturityNotice';
import { useI18n } from '@/i18n';

const { Dragger } = Upload;

// ========== 知识库卡片 ==========
function KnowledgeBaseCard({
  kb,
  onEdit,
  onDelete,
  onSelect,
}: {
  kb: KnowledgeBase;
  onEdit: (kb: KnowledgeBase) => void;
  onDelete: (id: string) => void;
  onSelect: (kb: KnowledgeBase) => void;
}) {
  const { t } = useI18n();
  const docCount = kb.documents.length;
  const completedDocs = kb.documents.filter((d) => d.status === 'completed').length;
  const processingDocs = kb.documents.filter((d) => d.status === 'processing').length;

  return (
    <Card
      hoverable
      style={{ height: '100%', cursor: 'pointer' }}
      onClick={() => onSelect(kb)}
      actions={[
        <Button type="link" icon={<EditOutlined />} onClick={(e) => { e.stopPropagation(); onEdit(kb); }}>
          {t('pages.knowledgeBase.card.edit')}
        </Button>,
        <Popconfirm
          title={t('pages.knowledgeBase.card.confirmDelete')}
          onConfirm={(e) => { if (e) { e.stopPropagation(); onDelete(kb.id); } }}
          onCancel={(e) => e?.stopPropagation()}
        >
          <Button type="link" danger icon={<DeleteOutlined />} onClick={(e) => e.stopPropagation()}>
            {t('pages.knowledgeBase.card.delete')}
          </Button>
        </Popconfirm>,
      ]}
    >
      <Card.Meta
        avatar={<DatabaseOutlined style={{ fontSize: 24, color: '#6366f1' }} />}
        title={kb.name}
        description={
          <div>
            <p style={{ color: '#888', margin: '8px 0' }}>{kb.description || t('pages.knowledgeBase.card.noDescription')}</p>
            <Space direction="vertical" size={4}>
              <Space>
                <FileTextOutlined />
                <span>{t('pages.knowledgeBase.card.docCount', { count: docCount, completed: completedDocs })}</span>
              </Space>
              {processingDocs > 0 && (
                <Tag color="processing">
                  {t('pages.knowledgeBase.card.processing', { count: processingDocs })}
                </Tag>
              )}
              <Space>
                <span style={{ fontSize: 12, color: '#888' }}>
                  {t('pages.knowledgeBase.card.chunkInfo', { size: kb.chunk_size, overlap: kb.chunk_overlap })}
                </span>
              </Space>
            </Space>
          </div>
        }
      />
    </Card>
  );
}

// ========== 知识库详情 ==========
function KnowledgeBaseDetail({ kb }: { kb: KnowledgeBase }) {
  const { t } = useI18n();
  const {
    addDocument, removeDocument, updateChunkConfig,
    startEmbedding, searchDocuments,
  } = useKnowledgeBaseStore();
  const [activeTab, setActiveTab] = useState('documents');
  const [, setUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<{ document: string; score: number; chunk: string }[]>([]);
  const [chunkSize, setChunkSize] = useState(kb.chunk_size);
  const [chunkOverlap, setChunkOverlap] = useState(kb.chunk_overlap);

  const handleUpload = (file: File) => {
    setUploading(true);
    const allowedTypes = ['.txt', '.md', '.pdf', '.docx'];
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();

    if (!allowedTypes.includes(ext)) {
      message.error(t('pages.knowledgeBase.messages.unsupportedFileType', { ext }));
      setUploading(false);
      return false;
    }

    // Simulate file upload
    addDocument(kb.id, {
      name: file.name,
      type: ext.slice(1),
      size: file.size,
      status: 'pending',
    });

    message.success(t('pages.knowledgeBase.messages.fileUploaded', { name: file.name }));
    setUploading(false);
    return false; // Prevent default upload
  };

  const handleStartEmbedding = () => {
    startEmbedding(kb.id);
    message.info(t('pages.knowledgeBase.messages.embeddingStarted'));
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      message.warning(t('pages.knowledgeBase.detail.search.enterContent'));
      return;
    }
    const results = await searchDocuments(kb.id, searchQuery);
    setSearchResults(results);
  };

  const handleSaveChunkConfig = () => {
    updateChunkConfig(kb.id, chunkSize, chunkOverlap);
    message.success(t('pages.knowledgeBase.messages.chunkConfigSaved'));
  };

  const docColumns: ColumnsType<DocumentDef> = [
    {
      title: t('pages.knowledgeBase.detail.columns.fileName'),
      dataIndex: 'name',
      key: 'name',
      render: (text) => (
        <Space>
          <FileTextOutlined />
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: t('pages.knowledgeBase.detail.columns.type'),
      dataIndex: 'type',
      key: 'type',
      width: 80,
      render: (text) => <Tag>{text}</Tag>,
    },
    {
      title: t('pages.knowledgeBase.detail.columns.size'),
      dataIndex: 'size',
      key: 'size',
      width: 100,
      render: (size: number) => `${(size / 1024).toFixed(1)} KB`,
    },
    {
      title: t('pages.knowledgeBase.detail.columns.status'),
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: DocumentDef['status']) => {
        const colors: Record<string, string> = {
          pending: 'default',
          processing: 'processing',
          completed: 'success',
          failed: 'error',
        };
        const labelKeys: Record<DocumentDef['status'], 'pages.knowledgeBase.detail.docStatus.pending' | 'pages.knowledgeBase.detail.docStatus.processing' | 'pages.knowledgeBase.detail.docStatus.completed' | 'pages.knowledgeBase.detail.docStatus.failed'> = {
          pending: 'pages.knowledgeBase.detail.docStatus.pending',
          processing: 'pages.knowledgeBase.detail.docStatus.processing',
          completed: 'pages.knowledgeBase.detail.docStatus.completed',
          failed: 'pages.knowledgeBase.detail.docStatus.failed',
        };
        return <Tag color={colors[status]}>{t(labelKeys[status])}</Tag>;
      },
    },
    {
      title: t('pages.knowledgeBase.detail.columns.chunks'),
      dataIndex: 'chunks_count',
      key: 'chunks_count',
      width: 80,
      render: (count?: number) => count ?? '-',
    },
    {
      title: t('pages.knowledgeBase.detail.columns.actions'),
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Popconfirm
          title={t('pages.knowledgeBase.detail.confirmDeleteDoc')}
          onConfirm={() => removeDocument(kb.id, record.id)}
        >
          <Button type="link" danger size="small" icon={<DeleteOutlined />}>
            {t('pages.knowledgeBase.detail.delete')}
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <DatabaseOutlined style={{ color: '#6366f1' }} />
          <span>{kb.name}</span>
        </Space>
      }
      extra={
        <Button onClick={() => window.history.back()}>
          {t('pages.knowledgeBase.detail.backToList')}
        </Button>
      }
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'documents',
            label: t('pages.knowledgeBase.detail.tabs.documents'),
            children: (
              <div>
                <div style={{ marginBottom: 16 }}>
                  <Dragger
                    customRequest={({ file }) => handleUpload(file as File)}
                    accept=".txt,.md,.pdf,.docx"
                    showUploadList={false}
                    multiple
                  >
                    <p className="ant-upload-drag-icon">
                      <UploadOutlined />
                    </p>
                    <p className="ant-upload-text">{t('pages.knowledgeBase.detail.upload.hint')}</p>
                    <p className="ant-upload-hint">{t('pages.knowledgeBase.detail.upload.formats')}</p>
                  </Dragger>
                </div>

                <Space style={{ marginBottom: 16 }}>
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={handleStartEmbedding}
                    disabled={kb.documents.every((d) => d.status !== 'pending')}
                  >
                    {t('pages.knowledgeBase.detail.startEmbedding')}
                  </Button>
                  <Tag color="blue">
                    {t('pages.knowledgeBase.detail.embeddingModel', { model: kb.embedding_model })}
                  </Tag>
                </Space>

                <Table
                  columns={docColumns}
                  dataSource={kb.documents}
                  rowKey="id"
                  pagination={{ pageSize: 10 }}
                  locale={{ emptyText: <Empty description={t('pages.knowledgeBase.detail.noDocuments')} /> }}
                />
              </div>
            ),
          },
          {
            key: 'chunking',
            label: t('pages.knowledgeBase.detail.tabs.chunking'),
            children: (
              <Card size="small" style={{ maxWidth: 600 }}>
                <Form layout="vertical">
                  <Form.Item label={t('pages.knowledgeBase.detail.chunk.size')}>
                    <Input
                      type="number"
                      value={chunkSize}
                      onChange={(e) => setChunkSize(Number(e.target.value))}
                      min={64}
                      max={4096}
                      addonAfter="tokens"
                    />
                  </Form.Item>
                  <Form.Item label={t('pages.knowledgeBase.detail.chunk.overlap')}>
                    <Input
                      type="number"
                      value={chunkOverlap}
                      onChange={(e) => setChunkOverlap(Number(e.target.value))}
                      min={0}
                      max={Math.floor(chunkSize / 2)}
                      addonAfter="tokens"
                    />
                  </Form.Item>
                  <Alert
                    message={t('pages.knowledgeBase.detail.chunk.hintTitle')}
                    description={t('pages.knowledgeBase.detail.chunk.hintDesc')}
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                  <Button type="primary" onClick={handleSaveChunkConfig}>
                    {t('pages.knowledgeBase.detail.chunk.save')}
                  </Button>
                </Form>
              </Card>
            ),
          },
          {
            key: 'search',
            label: t('pages.knowledgeBase.detail.tabs.search'),
            children: (
              <div>
                <Space style={{ marginBottom: 16 }} size="middle">
                  <Input
                    placeholder={t('pages.knowledgeBase.detail.search.placeholder')}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onPressEnter={handleSearch}
                    style={{ width: 400 }}
                    allowClear
                  />
                  <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
                    {t('pages.knowledgeBase.detail.search.search')}
                  </Button>
                </Space>

                {searchResults.length > 0 && (
                  <div>
                    <Divider orientation="left">{t('pages.knowledgeBase.detail.search.results', { count: searchResults.length })}</Divider>
                    {searchResults.map((result, index) => (
                      <Card
                        key={index}
                        size="small"
                        style={{ marginBottom: 12 }}
                        extra={
                          <Tag color={result.score > 0.8 ? 'green' : result.score > 0.5 ? 'orange' : 'default'}>
                            {t('pages.knowledgeBase.detail.search.similarity', { percent: (result.score * 100).toFixed(1) })}
                          </Tag>
                        }
                      >
                        <p style={{ margin: 0, fontWeight: 500 }}>
                          <FileTextOutlined /> {result.document}
                        </p>
                        <p style={{ color: '#666', margin: '8px 0 0' }}>{result.chunk}</p>
                      </Card>
                    ))}
                  </div>
                )}

                {searchResults.length === 0 && searchQuery && (
                  <Empty description={t('pages.knowledgeBase.detail.search.noResults')} />
                )}

                {!searchQuery && (
                  <Empty
                    description={t('pages.knowledgeBase.detail.search.startHint')}
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                  />
                )}
              </div>
            ),
          },
        ]}
      />
    </Card>
  );
}

// ========== 主页面 ==========
export default function KnowledgeBasePage() {
  const { t } = useI18n();
  const {
    knowledgeBases, selectedKbId, createKnowledgeBase,
    updateKnowledgeBase, deleteKnowledgeBase, selectKnowledgeBase,
    getKnowledgeBase, fetchKnowledgeBases,
  } = useKnowledgeBaseStore();
  const { mode } = useEngineStore();

  useEffect(() => {
    if (mode === 'real') {
      fetchKnowledgeBases();
    }
  }, [mode, fetchKnowledgeBases]);

  const [searchText, setSearchText] = useState('');
  const [modalVisible, setModalVisible] = useState(false);
  const [editingKb, setEditingKb] = useState<KnowledgeBase | null>(null);
  const [form] = Form.useForm();

  const selectedKb = selectedKbId ? getKnowledgeBase(selectedKbId) : null;

  const filteredKbs = knowledgeBases.filter((kb) =>
    kb.name.toLowerCase().includes(searchText.toLowerCase()) ||
    kb.description.toLowerCase().includes(searchText.toLowerCase())
  );

  const handleCreate = () => {
    setEditingKb(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (kb: KnowledgeBase) => {
    setEditingKb(kb);
    form.setFieldsValue({
      name: kb.name,
      description: kb.description,
      embedding_model: kb.embedding_model,
    });
    setModalVisible(true);
  };

  const handleDelete = (id: string) => {
    deleteKnowledgeBase(id);
    message.success(t('pages.knowledgeBase.messages.deleted'));
  };

  const handleModalOk = async () => {
    const values = await form.validateFields();
    if (editingKb) {
      updateKnowledgeBase(editingKb.id, values);
      message.success(t('pages.knowledgeBase.messages.updated'));
    } else {
      await createKnowledgeBase(values);
      message.success(t('pages.knowledgeBase.messages.created'));
    }
    setModalVisible(false);
  };

  const handleSelectKb = (kb: KnowledgeBase) => {
    selectKnowledgeBase(kb.id);
  };

  if (selectedKb) {
    return <KnowledgeBaseDetail kb={selectedKb} />;
  }

  return (
    <div>
      <PageMaturityNotice pageKey="knowledge" />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h3 style={{ margin: 0 }}>{t('pages.knowledgeBase.title')}</h3>
        <Space>
          <Input
            placeholder={t('pages.knowledgeBase.searchPlaceholder')}
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            {t('pages.knowledgeBase.create')}
          </Button>
        </Space>
      </div>

      {filteredKbs.length === 0 ? (
        <Empty
          description={searchText ? t('pages.knowledgeBase.emptySearch') : t('pages.knowledgeBase.empty')}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          {!searchText && (
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
              {t('pages.knowledgeBase.createFirst')}
            </Button>
          )}
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {filteredKbs.map((kb) => (
            <Col key={kb.id} xs={24} sm={12} lg={8} xl={6}>
              <KnowledgeBaseCard
                kb={kb}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onSelect={handleSelectKb}
              />
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title={editingKb ? t('pages.knowledgeBase.modal.editTitle') : t('pages.knowledgeBase.modal.createTitle')}
        open={modalVisible}
        onOk={handleModalOk}
        onCancel={() => setModalVisible(false)}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label={t('pages.knowledgeBase.form.name')}
            rules={[{ required: true, message: t('pages.knowledgeBase.form.nameRequired') }]}
          >
            <Input placeholder={t('pages.knowledgeBase.form.namePlaceholder')} />
          </Form.Item>
          <Form.Item name="description" label={t('pages.knowledgeBase.form.description')}>
            <Input.TextArea rows={3} placeholder={t('pages.knowledgeBase.form.descriptionPlaceholder')} />
          </Form.Item>
          <Form.Item name="embedding_model" label={t('pages.knowledgeBase.form.embeddingModel')}>
            <Select
              options={[
                { value: 'text-embedding-ada-002', label: 'OpenAI Ada-002' },
                { value: 'text-embedding-3-small', label: 'OpenAI Embedding 3 Small' },
                { value: 'text-embedding-3-large', label: 'OpenAI Embedding 3 Large' },
                { value: 'bge-large-zh', label: 'BGE Large ZH' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
