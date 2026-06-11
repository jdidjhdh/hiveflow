/**
 * HiveFlow - A/B 测试界面
 *
 * 用于比较两个 Agent/工作流配置的输出质量。
 * 支持：
 * - 实验创建（A/B 配置）
 * - 评估指标管理
 * - 结果对比可视化
 * - 历史记录
 */
import { useState, useCallback } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag,
  message, Card, Typography, Divider, Badge, Descriptions, Progress, Statistic, Row, Col, Alert, InputNumber,
} from 'antd';
import {
  PlusOutlined, ExperimentOutlined, TrophyOutlined, EyeOutlined, DeleteOutlined,
  ThunderboltOutlined, DiffOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

const { Title, Text } = Typography;

// ======================== Types ========================

interface Experiment {
  id: string;
  name: string;
  description: string;
  status: 'draft' | 'running' | 'completed' | 'failed';
  created_at: number;
  config_a: AgentConfig;
  config_b: AgentConfig;
  criteria: EvaluationCriterion[];
  results?: ABResult;
}

interface AgentConfig {
  name: string;
  model: string;
  temperature: number;
  prompt_template?: string;
  tools?: string[];
}

interface EvaluationCriterion {
  name: string;
  description: string;
  weight: number;
  threshold: number;
}

interface ABResult {
  winner: 'A' | 'B' | 'tie';
  score_a: number;
  score_b: number;
  score_diff: number;
  latency_a: number;
  latency_b: number;
  criteria_results: CriterionResult[];
  output_a: string;
  output_b: string;
}

interface CriterionResult {
  name: string;
  score_a: number;
  score_b: number;
  reason_a: string;
  reason_b: string;
  winner: 'A' | 'B' | 'tie';
}

// ======================== Mock Data ========================

const mockExperiments: Experiment[] = [
  {
    id: 'exp_001',
    name: 'GPT-4o vs Claude 3.5 - 代码生成',
    description: '比较 GPT-4o 和 Claude 3.5 Sonnet 在代码生成任务上的表现',
    status: 'completed',
    created_at: Date.now() - 86400000,
    config_a: { name: 'Agent A', model: 'gpt-4o', temperature: 0.2, tools: ['code_executor'] },
    config_b: { name: 'Agent B', model: 'claude-3-5-sonnet', temperature: 0.2, tools: ['code_executor'] },
    criteria: [
      { name: 'accuracy', description: '代码是否正确执行', weight: 1.5, threshold: 0.8 },
      { name: 'completeness', description: '是否覆盖所有需求', weight: 1.0, threshold: 0.7 },
      { name: 'safety', description: '是否存在安全隐患', weight: 1.2, threshold: 0.9 },
    ],
    results: {
      winner: 'B',
      score_a: 0.78,
      score_b: 0.85,
      score_diff: -0.07,
      latency_a: 2340,
      latency_b: 1890,
      criteria_results: [
        { name: 'accuracy', score_a: 0.82, score_b: 0.88, reason_a: '大部分正确', reason_b: '全部正确', winner: 'B' },
        { name: 'completeness', score_a: 0.75, score_b: 0.80, reason_a: '缺少边界处理', reason_b: '覆盖完整', winner: 'B' },
        { name: 'safety', score_a: 0.76, score_b: 0.88, reason_a: '输入验证不足', reason_b: '完整的验证', winner: 'B' },
      ],
      output_a: 'function calculate(items) {\n  return items.reduce((a, b) => a + b);\n}',
      output_b: 'function calculate(items: number[]): number {\n  if (!items?.length) return 0;\n  return items.reduce((sum, item) => sum + item, 0);\n}',
    },
  },
  {
    id: 'exp_002',
    name: '温度参数对比 - 0.0 vs 0.7',
    description: '测试不同 temperature 对输出创造性的影响',
    status: 'completed',
    created_at: Date.now() - 172800000,
    config_a: { name: '保守模式', model: 'gpt-4o', temperature: 0.0 },
    config_b: { name: '创造模式', model: 'gpt-4o', temperature: 0.7 },
    criteria: [
      { name: 'creativity', description: '输出的创造性程度', weight: 1.0, threshold: 0.6 },
      { name: 'accuracy', description: '事实准确性', weight: 1.5, threshold: 0.8 },
    ],
    results: {
      winner: 'tie',
      score_a: 0.82,
      score_b: 0.80,
      score_diff: 0.02,
      latency_a: 1200,
      latency_b: 1350,
      criteria_results: [
        { name: 'creativity', score_a: 0.60, score_b: 0.85, reason_a: '较为保守', reason_b: '富有创意', winner: 'B' },
        { name: 'accuracy', score_a: 0.95, score_b: 0.72, reason_a: '高度准确', reason_b: '偶有偏差', winner: 'A' },
      ],
      output_a: '这是一个标准的回答...',
      output_b: '让我从不同角度来分析这个问题...\n\n首先，我们可以考虑...',
    },
  },
];

// ======================== Main Component ========================

export default function ABTestingPage() {
  const [experiments, setExperiments] = useState<Experiment[]>(mockExperiments);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedExperiment, setSelectedExperiment] = useState<Experiment | null>(null);
  const [viewDrawerOpen, setViewDrawerOpen] = useState(false);
  const [form] = Form.useForm();

  // ======================== Create Experiment ========================

  const handleCreate = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const newExperiment: Experiment = {
        id: `exp_${Date.now().toString(36)}`,
        name: values.name,
        description: values.description || '',
        status: 'draft',
        created_at: Date.now(),
        config_a: {
          name: 'Agent A',
          model: values.model_a,
          temperature: values.temp_a ?? 0.2,
          tools: (values.tools_a || '').split(',').filter(Boolean),
        },
        config_b: {
          name: 'Agent B',
          model: values.model_b,
          temperature: values.temp_b ?? 0.2,
          tools: (values.tools_b || '').split(',').filter(Boolean),
        },
        criteria: values.criteria
          ? values.criteria.split('\n').filter(Boolean).map((line: string) => {
            const [name, desc, weight, threshold] = line.split('|').map((s: string) => s.trim());
            return {
              name: name || 'custom',
              description: desc || '',
              weight: parseFloat(weight) || 1.0,
              threshold: parseFloat(threshold) || 0.7,
            };
          })
          : [
            { name: 'accuracy', description: '输出准确性', weight: 1.5, threshold: 0.8 },
            { name: 'completeness', description: '输出完整性', weight: 1.0, threshold: 0.7 },
          ],
      };

      setExperiments((prev) => [newExperiment, ...prev]);
      setModalOpen(false);
      message.success('实验已创建');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg !== 'validateFields') {
        message.error('创建失败');
      }
    }
  }, [form]);

  // ======================== Run Experiment (Mock) ========================

  const handleRun = useCallback(async (experiment: Experiment) => {
    message.loading({ content: '正在运行实验...', key: 'running', duration: 0 });

    // Simulate running the experiment
    await new Promise((resolve) => setTimeout(resolve, 2000));

    const scoreA = 0.6 + Math.random() * 0.35;
    const scoreB = 0.6 + Math.random() * 0.35;
    const winner = scoreA > scoreB ? 'A' as const : scoreB > scoreA ? 'B' as const : 'tie' as const;

    const updated: Experiment = {
      ...experiment,
      status: 'completed',
      results: {
        winner,
        score_a: Math.round(scoreA * 100) / 100,
        score_b: Math.round(scoreB * 100) / 100,
        score_diff: Math.round((scoreA - scoreB) * 100) / 100,
        latency_a: 1000 + Math.floor(Math.random() * 2000),
        latency_b: 1000 + Math.floor(Math.random() * 2000),
        criteria_results: experiment.criteria.map((c) => {
          const sa = 0.5 + Math.random() * 0.45;
          const sb = 0.5 + Math.random() * 0.45;
          return {
            name: c.name,
            score_a: Math.round(sa * 100) / 100,
            score_b: Math.round(sb * 100) / 100,
            reason_a: `Agent A 在${c.description}方面表现${sa > 0.8 ? '优秀' : sa > 0.6 ? '良好' : '一般'}`,
            reason_b: `Agent B 在${c.description}方面表现${sb > 0.8 ? '优秀' : sb > 0.6 ? '良好' : '一般'}`,
            winner: sa > sb ? 'A' as const : sb > sa ? 'B' as const : 'tie' as const,
          };
        }),
        output_a: `Agent A (使用 ${experiment.config_a.model}) 的输出结果...`,
        output_b: `Agent B (使用 ${experiment.config_b.model}) 的输出结果...`,
      },
    };

    setExperiments((prev) => prev.map((e) => (e.id === experiment.id ? updated : e)));
    message.success({ content: '实验完成！', key: 'running' });
  }, []);

  // ======================== Delete Experiment ========================

  const handleDelete = useCallback((experiment: Experiment) => {
    setExperiments((prev) => prev.filter((e) => e.id !== experiment.id));
    message.success('实验已删除');
  }, []);

  // ======================== View Results ========================

  const handleViewResults = useCallback((experiment: Experiment) => {
    setSelectedExperiment(experiment);
    setViewDrawerOpen(true);
  }, []);

  // ======================== Columns ========================

  const columns: ColumnsType<Experiment> = [
    {
      title: '实验名称',
      dataIndex: 'name',
      key: 'name',
      width: 250,
      render: (name: string, record: Experiment) => (
        <Space direction="vertical" size={0}>
          <Text strong>{name}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{record.description}</Text>
        </Space>
      ),
    },
    {
      title: '配置 A',
      key: 'config_a',
      width: 200,
      render: (_: unknown, record: Experiment) => (
        <Space direction="vertical" size={0}>
          <Tag color="blue">{record.config_a.name}</Tag>
          <Text style={{ fontSize: 12 }}>模型: {record.config_a.model}</Text>
          <Text style={{ fontSize: 12 }}>温度: {record.config_a.temperature}</Text>
        </Space>
      ),
    },
    {
      title: '配置 B',
      key: 'config_b',
      width: 200,
      render: (_: unknown, record: Experiment) => (
        <Space direction="vertical" size={0}>
          <Tag color="green">{record.config_b.name}</Tag>
          <Text style={{ fontSize: 12 }}>模型: {record.config_b.model}</Text>
          <Text style={{ fontSize: 12 }}>温度: {record.config_b.temperature}</Text>
        </Space>
      ),
    },
    {
      title: '评估指标',
      key: 'criteria',
      width: 150,
      render: (_: unknown, record: Experiment) => (
        <Space wrap>
          {record.criteria.map((c) => (
            <Tag key={c.name} color="geekblue">{c.name}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '结果',
      key: 'result',
      width: 180,
      render: (_: unknown, record: Experiment) => {
        if (!record.results) return <Text type="secondary">未运行</Text>;
        const { winner, score_a, score_b } = record.results;
        return (
          <Space direction="vertical" size={2}>
            <Space>
              {winner === 'A' && <TrophyOutlined style={{ color: '#1890ff' }} />}
              {winner === 'B' && <TrophyOutlined style={{ color: '#52c41a' }} />}
              {winner === 'tie' && <DiffOutlined style={{ color: '#faad14' }} />}
              <Text strong>
                {winner === 'A' ? 'A 胜出' : winner === 'B' ? 'B 胜出' : '平局'}
              </Text>
            </Space>
            <Progress
              percent={Math.round((winner === 'A' ? score_a : score_b) * 100)}
              size="small"
              status="success"
              style={{ width: 150 }}
            />
          </Space>
        );
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const statusMap: Record<string, { color: string; text: string }> = {
          draft: { color: 'default', text: '草稿' },
          running: { color: 'processing', text: '运行中' },
          completed: { color: 'success', text: '已完成' },
          failed: { color: 'error', text: '失败' },
        };
        const s = statusMap[status] || { color: 'default', text: status };
        return <Badge color={s.color} text={s.text} />;
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_: unknown, record: Experiment) => (
        <Space>
          {record.status === 'draft' && (
            <Button
              size="small"
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={() => handleRun(record)}
            >
              运行
            </Button>
          )}
          {record.results && (
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handleViewResults(record)}
            >
              查看结果
            </Button>
          )}
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  // ======================== Render ========================

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Title level={4} style={{ margin: 0 }}>A/B 测试</Title>
          <Text type="secondary">比较不同 Agent 配置的输出质量</Text>
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建实验
        </Button>
      </div>

      {/* Summary Stats */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic title="总实验数" value={experiments.length} prefix={<ExperimentOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="已完成" value={experiments.filter((e) => e.status === 'completed').length} suffix="/ 次" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="A 胜出"
              value={experiments.filter((e) => e.results?.winner === 'A').length}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="B 胜出"
              value={experiments.filter((e) => e.results?.winner === 'B').length}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Experiment Table */}
      <Table
        columns={columns}
        dataSource={experiments}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />

      {/* Create Modal */}
      <Modal
        title="新建 A/B 测试"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        width={800}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="实验名称" rules={[{ required: true }]}>
            <Input placeholder="例如: GPT-4o vs Claude 3.5" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="实验描述" />
          </Form.Item>

          <Divider>配置 A</Divider>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="model_a" label="模型" rules={[{ required: true }]}>
                <Select options={[
                  { label: 'GPT-4o', value: 'gpt-4o' },
                  { label: 'GPT-4o-mini', value: 'gpt-4o-mini' },
                  { label: 'Claude 3.5 Sonnet', value: 'claude-3-5-sonnet' },
                  { label: 'Claude 3 Opus', value: 'claude-3-opus' },
                ]} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="temp_a" label="Temperature">
                <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="tools_a" label="工具（逗号分隔）">
            <Input placeholder="code_executor, web_search" />
          </Form.Item>

          <Divider>配置 B</Divider>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="model_b" label="模型" rules={[{ required: true }]}>
                <Select options={[
                  { label: 'GPT-4o', value: 'gpt-4o' },
                  { label: 'GPT-4o-mini', value: 'gpt-4o-mini' },
                  { label: 'Claude 3.5 Sonnet', value: 'claude-3-5-sonnet' },
                  { label: 'Claude 3 Opus', value: 'claude-3-opus' },
                ]} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="temp_b" label="Temperature">
                <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="tools_b" label="工具（逗号分隔）">
            <Input placeholder="code_executor, web_search" />
          </Form.Item>

          <Divider>评估指标</Divider>
          <Form.Item name="criteria" help="每行一个指标：名称 | 描述 | 权重 | 阈值">
            <Input.TextArea
              rows={4}
              placeholder={"accuracy | 输出准确性 | 1.5 | 0.8\ncompleteness | 输出完整性 | 1.0 | 0.7\nsafety | 安全性 | 1.2 | 0.9"}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Results Drawer */}
      {selectedExperiment?.results && (
        <Drawer
          title={`实验结果 - ${selectedExperiment.name}`}
          open={viewDrawerOpen}
          onClose={() => setViewDrawerOpen(false)}
          width={900}
        >
          <ResultsView experiment={selectedExperiment} />
        </Drawer>
      )}
    </div>
  );
}

// ======================== Results View Component ========================

function ResultsView({ experiment }: { experiment: Experiment }) {
  const results = experiment.results!;

  return (
    <div>
      {/* Winner Banner */}
      <Alert
        message={
          <Space>
            <TrophyOutlined style={{ color: '#faad14', fontSize: 20 }} />
            <Text strong style={{ fontSize: 16 }}>
              {results.winner === 'tie' ? '平局！' : `${results.winner} 配置胜出！`}
            </Text>
          </Space>
        }
        description={`综合评分: A=${results.score_a.toFixed(2)} vs B=${results.score_b.toFixed(2)} | 差距: ${results.score_diff > 0 ? '+' : ''}${results.score_diff.toFixed(2)}`}
        type={results.winner === 'tie' ? 'warning' : 'success'}
        showIcon={false}
        style={{ marginBottom: 16 }}
      />

      {/* Score Comparison */}
      <Card title="综合评分对比" style={{ marginBottom: 16 }}>
        <Row gutter={24}>
          <Col span={12}>
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="配置">{experiment.config_a.name}</Descriptions.Item>
              <Descriptions.Item label="模型">{experiment.config_a.model}</Descriptions.Item>
              <Descriptions.Item label="温度">{experiment.config_a.temperature}</Descriptions.Item>
              <Descriptions.Item label="综合评分">
                <Progress
                  percent={Math.round(results.score_a * 100)}
                  status={results.winner === 'A' ? 'success' : 'normal'}
                />
              </Descriptions.Item>
              <Descriptions.Item label="延迟">{results.latency_a}ms</Descriptions.Item>
            </Descriptions>
          </Col>
          <Col span={12}>
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="配置">{experiment.config_b.name}</Descriptions.Item>
              <Descriptions.Item label="模型">{experiment.config_b.model}</Descriptions.Item>
              <Descriptions.Item label="温度">{experiment.config_b.temperature}</Descriptions.Item>
              <Descriptions.Item label="综合评分">
                <Progress
                  percent={Math.round(results.score_b * 100)}
                  status={results.winner === 'B' ? 'success' : 'normal'}
                />
              </Descriptions.Item>
              <Descriptions.Item label="延迟">{results.latency_b}ms</Descriptions.Item>
            </Descriptions>
          </Col>
        </Row>
      </Card>

      {/* Criteria Results */}
      <Card title="评估指标详情" style={{ marginBottom: 16 }}>
        <Table
          dataSource={results.criteria_results}
          rowKey="name"
          pagination={false}
          columns={[
            {
              title: '指标',
              dataIndex: 'name',
              key: 'name',
              width: 120,
              render: (name: string) => <Tag color="geekblue">{name}</Tag>,
            },
            {
              title: 'A 得分',
              dataIndex: 'score_a',
              key: 'score_a',
              width: 100,
              render: (score: number, record: CriterionResult) => (
                <Space>
                  <Progress
                    percent={Math.round(score * 100)}
                    size="small"
                    status={record.winner === 'A' ? 'success' : 'normal'}
                    style={{ width: 80 }}
                  />
                  {score.toFixed(2)}
                </Space>
              ),
            },
            {
              title: 'B 得分',
              dataIndex: 'score_b',
              key: 'score_b',
              width: 100,
              render: (score: number, record: CriterionResult) => (
                <Space>
                  <Progress
                    percent={Math.round(score * 100)}
                    size="small"
                    status={record.winner === 'B' ? 'success' : 'normal'}
                    style={{ width: 80 }}
                  />
                  {score.toFixed(2)}
                </Space>
              ),
            },
            {
              title: '胜出',
              dataIndex: 'winner',
              key: 'winner',
              width: 80,
              render: (w: string) => (
                w === 'tie'
                  ? <Tag>平局</Tag>
                  : <Tag color={w === 'A' ? 'blue' : 'green'}>{w}</Tag>
              ),
            },
            {
              title: 'A 评价',
              dataIndex: 'reason_a',
              key: 'reason_a',
            },
            {
              title: 'B 评价',
              dataIndex: 'reason_b',
              key: 'reason_b',
            },
          ]}
        />
      </Card>

      {/* Output Comparison */}
      <Card title="输出对比">
        <Row gutter={16}>
          <Col span={12}>
            <Card size="small" title={`Agent A (${experiment.config_a.model})`}>
              <pre style={{
                background: '#f5f5f5',
                padding: 12,
                borderRadius: 4,
                whiteSpace: 'pre-wrap',
                maxHeight: 300,
                overflow: 'auto',
                fontSize: 12,
              }}>
                {results.output_a}
              </pre>
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title={`Agent B (${experiment.config_b.model})`}>
              <pre style={{
                background: '#f5f5f5',
                padding: 12,
                borderRadius: 4,
                whiteSpace: 'pre-wrap',
                maxHeight: 300,
                overflow: 'auto',
                fontSize: 12,
              }}>
                {results.output_b}
              </pre>
            </Card>
          </Col>
        </Row>
      </Card>
    </div>
  );
}

function Drawer({ title, open, onClose, width, children }: {
  title: string;
  open: boolean;
  onClose: () => void;
  width: number;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: open ? 0 : -width,
        width,
        height: '100vh',
        background: '#fff',
        boxShadow: '-4px 0 12px rgba(0,0,0,0.15)',
        transition: 'right 0.3s ease',
        zIndex: 1000,
        overflow: 'auto',
        padding: 24,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0 }}>{title}</Title>
        <Button onClick={onClose}>关闭</Button>
      </div>
      {children}
    </div>
  );
}
