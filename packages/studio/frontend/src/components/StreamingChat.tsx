/**
 * HiveFlow - 流式响应实时展示组件
 *
 * 使用 Server-Sent Events (SSE) 接收后端实时事件流，
 * 以打字机效果展示 LLM 生成过程。
 *
 * 支持 9 种事件类型：
 * - token: LLM 生成的 token
 * - thought: Agent 思考过程
 * - tool_call: 工具调用
 * - tool_result: 工具返回结果
 * - checkpoint: 检查点保存
 * - node_start: 节点开始
 * - node_end: 节点结束
 * - error: 错误事件
 * - done: 流结束
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Card, Typography, Spin, Space, Tag, Button, Collapse,
  Alert, Badge, Divider, List, Tooltip,
} from 'antd';
import {
  LoadingOutlined, ThunderboltOutlined, ToolOutlined,
  CheckCircleOutlined, CloseCircleOutlined, PlayCircleOutlined,
  StopOutlined, ClockCircleOutlined, FileTextOutlined,
  PauseCircleOutlined,
} from '@ant-design/icons';
import { API_BASE_URL } from '@/utils/api';
import ReactMarkdown from 'react-markdown';

const { Text, Paragraph } = Typography;

// ======================== Types ========================

type StreamEventType =
  | 'token' | 'thought' | 'tool_call' | 'tool_result'
  | 'checkpoint' | 'node_start' | 'node_end' | 'error' | 'done';

interface StreamEvent {
  type: StreamEventType;
  data: string | Record<string, unknown>;
  timestamp: number;
  node_id?: string;
  workflow_id?: string;
  metadata?: Record<string, unknown>;
}

interface StreamingChatProps {
  endpoint?: string;  // SSE endpoint (relative to API_BASE_URL)
  workflowId?: string;
  /** Auto-connect on mount */
  autoConnect?: boolean;
  /** Callback when stream is done */
  onDone?: (events: StreamEvent[]) => void;
  /** Max displayed events */
  maxEvents?: number;
}

// ======================== Event Icon Mapping ========================

const eventIcon: Record<StreamEventType, JSX.Element> = {
  token: <FileTextOutlined />,
  thought: <ClockCircleOutlined />,
  tool_call: <ToolOutlined />,
  tool_result: <CheckCircleOutlined />,
  checkpoint: <PauseCircleOutlined />,
  node_start: <PlayCircleOutlined />,
  node_end: <StopOutlined />,
  error: <CloseCircleOutlined />,
  done: <CheckCircleOutlined />,
};

const eventColors: Record<StreamEventType, string> = {
  token: 'blue',
  thought: 'orange',
  tool_call: 'purple',
  tool_result: 'green',
  checkpoint: 'cyan',
  node_start: 'geekblue',
  node_end: 'volcano',
  error: 'red',
  done: 'success',
};

const eventLabels: Record<StreamEventType, string> = {
  token: 'Token',
  thought: '思考',
  tool_call: '工具调用',
  tool_result: '工具结果',
  checkpoint: '检查点',
  node_start: '节点开始',
  node_end: '节点结束',
  error: '错误',
  done: '完成',
};

// ======================== Main Component ========================

export default function StreamingChat({
  endpoint = '/api/stream',
  workflowId,
  autoConnect = false,
  onDone,
  maxEvents = 200,
}: StreamingChatProps) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Accumulated text for token events
  const [accumulatedText, setAccumulatedText] = useState('');
  const [thoughts, setThoughts] = useState<string[]>([]);
  const [toolCalls, setToolCalls] = useState<Array<{ name: string; args: string; result: string }>>([]);
  const [nodeStatuses, setNodeStatuses] = useState<Record<string, 'running' | 'done' | 'error'>>({});

  // Auto-scroll to bottom
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [accumulatedText, events]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  // ======================== Connection ========================

  const connect = useCallback(() => {
    // Close existing connection
    eventSourceRef.current?.close();

    const url = `${API_BASE_URL}${endpoint}${workflowId ? `?workflow_id=${workflowId}` : ''}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      setConnected(true);
      setError(null);
      setLoading(false);
    };

    // Register handlers for each event type
    const eventTypes: StreamEventType[] = [
      'token', 'thought', 'tool_call', 'tool_result',
      'checkpoint', 'node_start', 'node_end', 'error', 'done',
    ];

    for (const eventType of eventTypes) {
      es.addEventListener(eventType, (e) => {
        try {
          const data = JSON.parse(e.data);
          const event: StreamEvent = {
            type: eventType,
            data,
            timestamp: Date.now(),
            node_id: data.node_id,
            workflow_id: data.workflow_id,
            metadata: data.metadata,
          };

          setEvents((prev) => [...prev.slice(-maxEvents + 1), event]);

          // Update accumulated state based on event type
          switch (eventType) {
            case 'token':
              setAccumulatedText((prev) => prev + (typeof data === 'string' ? data : String(data)));
              break;
            case 'thought':
              setThoughts((prev) => [...prev, typeof data === 'string' ? data : String(data)]);
              break;
            case 'tool_call':
              setToolCalls((prev) => [
                ...prev,
                { name: String(data?.name || ''), args: JSON.stringify(data?.args || data), result: '' },
              ]);
              break;
            case 'tool_result':
              setToolCalls((prev) => {
                const updated = [...prev];
                if (updated.length > 0) {
                  updated[updated.length - 1].result = JSON.stringify(data);
                }
                return updated;
              });
              break;
            case 'node_start':
              if (data?.node_id) {
                setNodeStatuses((prev) => ({ ...prev, [String(data.node_id)]: 'running' }));
              }
              break;
            case 'node_end':
              if (data?.node_id) {
                setNodeStatuses((prev) => ({ ...prev, [String(data.node_id)]: 'done' }));
              }
              break;
            case 'error':
              setError(typeof data === 'string' ? data : JSON.stringify(data));
              break;
            case 'done':
              es.close();
              setConnected(false);
              onDone?.(events);
              break;
          }
        } catch {
          // Ignore parse errors for raw text tokens
          if (eventType === 'token') {
            setAccumulatedText((prev) => prev + e.data);
          }
        }
      });
    }

    es.onerror = () => {
      setConnected(false);
      setError('连接断开');
      es.close();
    };
  }, [endpoint, workflowId, onDone, events, maxEvents]);

  const disconnect = useCallback(() => {
    eventSourceRef.current?.close();
    setConnected(false);
  }, []);

  const clear = useCallback(() => {
    setEvents([]);
    setAccumulatedText('');
    setThoughts([]);
    setToolCalls([]);
    setNodeStatuses({});
    setError(null);
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ======================== Stats ========================

  const tokenCount = events.filter((e) => e.type === 'token').length;
  const thoughtCount = events.filter((e) => e.type === 'thought').length;
  const toolCallCount = events.filter((e) => e.type === 'tool_call').length;
  const errorCount = events.filter((e) => e.type === 'error').length;
  const duration = events.length > 0
    ? ((events[events.length - 1].timestamp || Date.now()) - (events[0].timestamp || Date.now())) / 1000
    : 0;

  // ======================== Render ========================

  return (
    <Card
      title={
        <Space>
          <ThunderboltOutlined />
          <span>流式响应</span>
          <Badge status={connected ? 'processing' : 'default'} text={connected ? '连接中' : '未连接'} />
        </Space>
      }
      extra={
        <Space>
          {!connected ? (
            <Button type="primary" size="small" onClick={connect} loading={loading}>
              连接
            </Button>
          ) : (
            <Button danger size="small" onClick={disconnect}>
              断开
            </Button>
          )}
          <Button size="small" onClick={clear}>
            清空
          </Button>
        </Space>
      }
      style={{ height: '100%' }}
      bodyStyle={{ padding: '12px 16px', maxHeight: 'calc(100vh - 200px)', overflow: 'auto' }}
    >
      {/* Stats Bar */}
      <div style={{ marginBottom: 12 }}>
        <Space wrap size="small">
          <Tag color="blue" icon={<FileTextOutlined />}>Tokens: {tokenCount}</Tag>
          <Tag color="orange" icon={<ClockCircleOutlined />}>思考: {thoughtCount}</Tag>
          <Tag color="purple" icon={<ToolOutlined />}>工具: {toolCallCount}</Tag>
          {errorCount > 0 && <Tag color="red" icon={<CloseCircleOutlined />}>错误: {errorCount}</Tag>}
          <Tag icon={<ClockCircleOutlined />}>耗时: {duration.toFixed(1)}s</Tag>
        </Space>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert
          message="错误"
          description={error}
          type="error"
          showIcon
          closable
          onClose={() => setError(null)}
          style={{ marginBottom: 12 }}
        />
      )}

      {/* Generated Content */}
      {accumulatedText && (
        <div style={{ marginBottom: 16 }}>
          <Divider orientation="left">生成内容</Divider>
          <div
            ref={containerRef}
            style={{
              background: '#fafafa',
              padding: 16,
              borderRadius: 8,
              maxHeight: 300,
              overflow: 'auto',
              lineHeight: 1.8,
            }}
          >
            {accumulatedText.endsWith('▌') ? (
              <Text>
                {accumulatedText.slice(0, -1)}
                <Spin size="small" />
              </Text>
            ) : (
              <ReactMarkdown>{accumulatedText}</ReactMarkdown>
            )}
          </div>
        </div>
      )}

      {/* Thinking Process */}
      {thoughts.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Divider orientation="left">思考过程</Divider>
          <Collapse size="small" ghost>
            {thoughts.map((t, i) => (
              <Collapse.Panel
                key={i}
                header={`思考 #${i + 1}`}
              >
                <Paragraph style={{ margin: 0 }}>{t}</Paragraph>
              </Collapse.Panel>
            ))}
          </Collapse>
        </div>
      )}

      {/* Tool Calls */}
      {toolCalls.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Divider orientation="left">工具调用</Divider>
          <List
            size="small"
            dataSource={toolCalls}
            renderItem={(tc, i) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <ToolOutlined />
                      <Text strong>{tc.name || `Tool #${i + 1}`}</Text>
                      {tc.result && <Tag color="green">完成</Tag>}
                    </Space>
                  }
                  description={
                    <Space direction="vertical" size={0} style={{ width: '100%' }}>
                      <Text code style={{ fontSize: 12 }}>{tc.args}</Text>
                      {tc.result && (
                        <Text type="secondary" style={{ fontSize: 12 }}>{tc.result.slice(0, 100)}</Text>
                      )}
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        </div>
      )}

      {/* Node Status */}
      {Object.keys(nodeStatuses).length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Divider orientation="left">节点状态</Divider>
          <Space wrap>
            {Object.entries(nodeStatuses).map(([nodeId, status]) => (
              <Tooltip key={nodeId} title={nodeId}>
                <Tag
                  color={status === 'running' ? 'processing' : status === 'done' ? 'success' : 'error'}
                  icon={
                    status === 'running' ? <LoadingOutlined />
                      : status === 'done' ? <CheckCircleOutlined />
                        : <CloseCircleOutlined />
                  }
                >
                  {nodeId.slice(0, 8)}
                </Tag>
              </Tooltip>
            ))}
          </Space>
        </div>
      )}

      {/* Event Timeline */}
      {events.length > 0 && (
        <div>
          <Divider orientation="left">事件时间线 ({events.length})</Divider>
          <div style={{ maxHeight: 200, overflow: 'auto' }}>
            {events.map((event, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '4px 8px',
                  borderBottom: '1px solid #f0f0f0',
                  fontSize: 12,
                }}
              >
                <Tag
                  color={eventColors[event.type]}
                  icon={eventIcon[event.type]}
                  style={{ margin: '0 8px 0 0', fontSize: 10 }}
                >
                  {eventLabels[event.type]}
                </Tag>
                <Text type="secondary" style={{ fontSize: 10, marginRight: 8 }}>
                  {new Date(event.timestamp).toLocaleTimeString()}
                </Text>
                <Text ellipsis style={{ maxWidth: 300, fontSize: 11 }}>
                  {typeof event.data === 'string'
                    ? event.data.slice(0, 50)
                    : JSON.stringify(event.data).slice(0, 50)}
                </Text>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {events.length === 0 && !connected && !error && (
        <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
          <ThunderboltOutlined style={{ fontSize: 48, marginBottom: 16 }} />
          <div>点击"连接"开始接收实时事件流</div>
        </div>
      )}
    </Card>
  );
}
