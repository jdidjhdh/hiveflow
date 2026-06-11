// ========== 数据模型定义 ==========

// 期望输出
export interface Expectation {
  state_key: string;
  expected_schema: Record<string, unknown>;
  validation: string;
  deadline: number;
  use_json_schema: boolean;
}

// ECM 消息
export interface ECM {
  trace_id: string;
  intent: string;
  intent_id: string;
  emitter: string;
  expectation?: Expectation;
  payload: Record<string, unknown>;
  reply_to: string;
  timestamp: number;
  required_skills: string[];
  priority: string;
  metadata: Record<string, unknown>;
}

// AI 模型配置
export interface ModelConfig {
  provider: 'openai' | 'anthropic' | 'ollama' | 'custom';
  model_name: string;
  api_key?: string;
  system_prompt?: string;
  tools?: string[];
  temperature?: number;
}

// Agent 最近任务
export interface AgentTaskRecord {
  timestamp: number;
  intent_id: string;
  status: 'success' | 'failed' | 'timeout';
  duration: number;
}

// Agent 能力
export interface Capability {
  agent_id: string;
  display_name: string;
  description?: string;
  icon?: string;
  skills: string[];
  load: number;
  history: number[];
  load_history: { time: number; load: number }[];
  recent_tasks: AgentTaskRecord[];
  read_keys: string[];
  write_keys: string[];
  state: 'starting' | 'running' | 'draining' | 'stopped';
  weight: number;
  pending_tasks: number;
  task_handler?: string;
  model_config?: ModelConfig;
  last_heartbeat: number;
}

// 外部服务调用配置
export interface ExternalServiceConfig {
  service_name: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  url: string;
  headers: { key: string; value: string }[];
  query_params: { key: string; value: string }[];
  body: string;
  timeout: number;
  output_mapping: string;
  blackboard_key: string;
}

// 能力定义
export type CapabilitySource = 'preset' | 'external_service' | 'upload' | 'online_edit';

export interface CapabilityDef {
  id: string;
  name: string;
  source: CapabilitySource;
  created_at: number;
  agent_count: number;
  description?: string;
  config?: ExternalServiceConfig;
  code?: string;
}

// 任务图定义
export interface TaskNodeDef {
  task: string;
  depends_on: string[];
  retry_policy?: {
    max_attempts: number;
    backoff_type: 'constant' | 'exponential';
    backoff_base: number;
    max_backoff: number;
  };
  on_failure?: 'abort' | 'skip';
  dynamic?: boolean;
  expectation?: Expectation;
  required_skills?: string[];
  variant?: string;
  hitl_config?: {
    prompt?: string;
    action?: 'approval' | 'review' | 'input' | 'confirmation';
    timeout_seconds?: number;
    on_timeout?: 'fail' | 'approve' | 'skip';
  };
}

export interface TaskGraph {
  [nodeName: string]: TaskNodeDef;
}

// 审计条目
export interface AuditEntry {
  action: 'get' | 'put' | 'wait';
  agent: string;
  key: string;
  timestamp: number;
}

// 指标快照
export interface MetricsSnapshot {
  counters: Record<string, number>;
  gauges: Record<string, number>;
}

// 事件记录
export interface EventRecord {
  timestamp: number;
  topic: string;
  data: ECM;
}

// ========== React Flow 节点/边类型扩展 ==========
export interface WorkflowNodeData {
  label: string;
  task: string;
  skills: string[];
  variant?: 'task' | 'dynamic' | 'subgraph' | 'condition' | 'loop' | 'code' | 'http' | 'trigger' | 'hitl';
  hitl_config?: TaskNodeDef['hitl_config'];
  expectation?: Expectation;
  retry_policy?: TaskNodeDef['retry_policy'];
  on_failure?: 'abort' | 'skip';
  dynamic?: boolean;
  status: 'idle' | 'pending' | 'running' | 'completed' | 'failed';
  result?: unknown;
  error?: string;
}

export type WorkflowNodeType = 'taskNode' | 'startNode' | 'endNode' | 'dynamicNode' | 'subgraphNode' | 'conditionNode' | 'loopNode' | 'codeNode' | 'httpNode' | 'triggerNode';

// 条件分支节点
export interface ConditionNodeData {
  condition: string;  // JS表达式，如 "{{input.value}} > 10"
  branches: { id: string; label: string; condition: string }[];
  default_branch?: string;
}

// 变量定义
export interface VariableDef {
  id: string;
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  value: unknown;
  scope: 'global' | 'local';
  description?: string;
}

// 执行日志
export interface ExecutionLog {
  id: string;
  workflow_id: string;
  node_id?: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  timestamp: number;
  data?: unknown;
}

// 触发器
export interface TriggerDef {
  id: string;
  name: string;
  type: 'webhook' | 'schedule' | 'event';
  config: Record<string, unknown>;
  enabled: boolean;
  workflow_id?: string;
  created_at?: number;
}

// 凭证
export interface Credential {
  id: string;
  name: string;
  type: string;
  created_at: number;
}

// LLM 配置
export interface LLMProviderConfig {
  id: string;
  name: string;
  provider: 'openai' | 'anthropic' | 'ollama' | 'custom';
  model_name: string;
  api_key_credential_id?: string;
  base_url?: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
}

// 代码执行节点
export interface CodeNodeData {
  language: 'python' | 'javascript';
  code: string;
  input_mapping: Record<string, string>;
  output_mapping: Record<string, string>;
}

// ========== 知识库 RAG ==========
export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  documents: DocumentDef[];
  embedding_model: string;
  chunk_size: number;
  chunk_overlap: number;
  created_at: number;
  updated_at: number;
  doc_count?: number;
}

export interface DocumentDef {
  id: string;
  name: string;
  type: string;
  size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  chunks_count?: number;
  content?: string;
  created_at: number;
}

// Chatflow 节点
export interface ChatflowNodeData {
  label: string;
  nodeType: 'user_input' | 'ai_reply' | 'condition' | 'variable';
  prompt?: string;
  variable_mapping?: Record<string, string>;
  condition?: string;
}

// ========== 插件市场 ==========
export interface PluginCategory {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  count?: number;
}

export interface PluginMarketplaceItem {
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

export interface PluginDetail {
  plugin_id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  author: string;
  status: 'available' | 'installed';
  tags: string[];
  created_at: number;
  capabilities: string[];
  readme?: string;
  config_schema?: Record<string, unknown>;
}

export interface InstalledPlugin {
  plugin_id: string;
  name: string;
  version: string;
  category: string;
  enabled: boolean;
  installed_at: number;
}

// ========== 分析数据 ==========
export interface AnalyticsSummary {
  total_executions: number;
  success_count: number;
  failed_count: number;
  success_rate: number;
  avg_duration: number;
  total_duration: number;
}

export interface ExecutionTrend {
  date: string;
  executions: number;
  successes: number;
  failures: number;
  avg_duration: number;
}

export interface NodeDurationRank {
  node_name: string;
  avg_duration: number;
  max_duration: number;
  min_duration: number;
  call_count: number;
}

export interface AgentLoadDist {
  agent_id: string;
  display_name: string;
  execution_count: number;
  avg_load: number;
  success_rate: number;
}

export interface ErrorTypeStat {
  error_type: string;
  count: number;
  percentage: number;
}

export interface AnalyticsData {
  summary: AnalyticsSummary;
  trends: ExecutionTrend[];
  node_rankings: NodeDurationRank[];
  agent_load: AgentLoadDist[];
  error_stats: ErrorTypeStat[];
  recent_executions: {
    id: string;
    workflow_id: string;
    status: 'success' | 'failed' | 'timeout';
    duration: number;
    timestamp: number;
    node_count: number;
  }[];
}