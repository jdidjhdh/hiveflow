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
          编辑
        </Button>,
        <Popconfirm
          title="确定删除此知识库？"
          onConfirm={(e) => { if (e) { e.stopPropagation(); onDelete(kb.id); } }}
          onCancel={(e) => e?.stopPropagation()}
        >
          <Button type="link" danger icon={<DeleteOutlined />} onClick={(e) => e.stopPropagation()}>
            删除
          </Button>
        </Popconfirm>,
      ]}
    >
      <Card.Meta
        avatar={<DatabaseOutlined style={{ fontSize: 24, color: '#6366f1' }} />}
        title={kb.name}
        description={
          <div>
            <p style={{ color: '#888', margin: '8px 0' }}>{kb.description || '暂无描述'}</p>
            <Space direction="vertical" size={4}>
              <Space>
                <FileTextOutlined />
                <span>{docCount} 个文档（{completedDocs} 已完成）</span>
              </Space>
              {processingDocs > 0 && (
                <Tag color="processing">
                  {processingDocs} 个文档处理中
                </Tag>
              )}
              <Space>
                <span style={{ fontSize: 12, color: '#888' }}>
                  切片: {kb.chunk_size} / 重叠: {kb.chunk_overlap}
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
      message.error(`不支持的文件类型：${ext}`);
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

    message.success(`文件 ${file.name} 已上传`);
    setUploading(false);
    return false; // Prevent default upload
  };

  const handleStartEmbedding = () => {
    startEmbedding(kb.id);
    message.info('开始向量化处理...');
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      message.warning('请输入搜索内容');
      return;
    }
    const results = await searchDocuments(kb.id, searchQuery);
    setSearchResults(results);
  };

  const handleSaveChunkConfig = () => {
    updateChunkConfig(kb.id, chunkSize, chunkOverlap);
    message.success('切片配置已保存');
  };

  const docColumns: ColumnsType<DocumentDef> = [
    {
      title: '文件名',
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
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 80,
      render: (text) => <Tag>{text}</Tag>,
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: 100,
      render: (size: number) => `${(size / 1024).toFixed(1)} KB`,
    },
    {
      title: '状态',
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
        const labels: Record<string, string> = {
          pending: '待处理',
          processing: '处理中',
          completed: '已完成',
          failed: '失败',
        };
        return <Tag color={colors[status]}>{labels[status]}</Tag>;
      },
    },
    {
      title: '切片数',
      dataIndex: 'chunks_count',
      key: 'chunks_count',
      width: 80,
      render: (count?: number) => count ?? '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Popconfirm
          title="确定删除此文档？"
          onConfirm={() => removeDocument(kb.id, record.id)}
        >
          <Button type="link" danger size="small" icon={<DeleteOutlined />}>
            删除
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
          返回列表
        </Button>
      }
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'documents',
            label: '文档管理',
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
                    <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
                    <p className="ant-upload-hint">支持 .txt / .md / .pdf / .docx 格式</p>
                  </Dragger>
                </div>

                <Space style={{ marginBottom: 16 }}>
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={handleStartEmbedding}
                    disabled={kb.documents.every((d) => d.status !== 'pending')}
                  >
                    开始向量化
                  </Button>
                  <Tag color="blue">
                    向量化模型: {kb.embedding_model}
                  </Tag>
                </Space>

                <Table
                  columns={docColumns}
                  dataSource={kb.documents}
                  rowKey="id"
                  pagination={{ pageSize: 10 }}
                  locale={{ emptyText: <Empty description="暂无文档" /> }}
                />
              </div>
            ),
          },
          {
            key: 'chunking',
            label: '切片配置',
            children: (
              <Card size="small" style={{ maxWidth: 600 }}>
                <Form layout="vertical">
                  <Form.Item label="切片大小 (Chunk Size)">
                    <Input
                      type="number"
                      value={chunkSize}
                      onChange={(e) => setChunkSize(Number(e.target.value))}
                      min={64}
                      max={4096}
                      addonAfter="tokens"
                    />
                  </Form.Item>
                  <Form.Item label="重叠大小 (Overlap)">
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
                    message="提示"
                    description="较大的切片大小会保留更多上下文，但可能降低检索精度。重叠部分有助于保持语义连贯性。"
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                  <Button type="primary" onClick={handleSaveChunkConfig}>
                    保存配置
                  </Button>
                </Form>
              </Card>
            ),
          },
          {
            key: 'search',
            label: '检索测试',
            children: (
              <div>
                <Space style={{ marginBottom: 16 }} size="middle">
                  <Input
                    placeholder="输入检索内容..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onPressEnter={handleSearch}
                    style={{ width: 400 }}
                    allowClear
                  />
                  <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
                    检索
                  </Button>
                </Space>

                {searchResults.length > 0 && (
                  <div>
                    <Divider orientation="left">检索结果 ({searchResults.length})</Divider>
                    {searchResults.map((result, index) => (
                      <Card
                        key={index}
                        size="small"
                        style={{ marginBottom: 12 }}
                        extra={
                          <Tag color={result.score > 0.8 ? 'green' : result.score > 0.5 ? 'orange' : 'default'}>
                            相似度: {(result.score * 100).toFixed(1)}%
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
                  <Empty description="未找到相关结果" />
                )}

                {!searchQuery && (
                  <Empty
                    description="输入内容开始测试向量检索"
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
    message.success('知识库已删除');
  };

  const handleModalOk = async () => {
    const values = await form.validateFields();
    if (editingKb) {
      updateKnowledgeBase(editingKb.id, values);
      message.success('知识库已更新');
    } else {
      await createKnowledgeBase(values);
      message.success('知识库已创建');
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h3 style={{ margin: 0 }}>知识库管理</h3>
        <Space>
          <Input
            placeholder="搜索知识库..."
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            新建知识库
          </Button>
        </Space>
      </div>

      {filteredKbs.length === 0 ? (
        <Empty
          description={searchText ? '未找到匹配的知识库' : '暂无知识库，点击上方按钮创建'}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          {!searchText && (
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
              创建第一个知识库
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
        title={editingKb ? '编辑知识库' : '新建知识库'}
        open={modalVisible}
        onOk={handleModalOk}
        onCancel={() => setModalVisible(false)}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="知识库名称"
            rules={[{ required: true, message: '请输入知识库名称' }]}
          >
            <Input placeholder="例如：产品文档知识库" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="描述此知识库的用途" />
          </Form.Item>
          <Form.Item name="embedding_model" label="向量化模型">
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
