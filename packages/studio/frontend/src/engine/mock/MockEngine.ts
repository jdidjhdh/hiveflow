import type { ECM, Capability, AuditEntry, MetricsSnapshot, TaskGraph, TaskNodeDef, ExecutionLog, ConditionNodeData } from '@/types';

// ========== 日志收集器 ==========
class MockLogCollector {
  private logs: ExecutionLog[] = [];

  addLog(log: Omit<ExecutionLog, 'id'>) {
    const entry: ExecutionLog = { ...log, id: `log_${Date.now()}_${Math.random().toString(36).slice(2, 8)}` };
    this.logs.push(entry);
  }

  getLogs(): ExecutionLog[] {
    return [...this.logs];
  }

  clearLogs() {
    this.logs = [];
  }
}

// ========== 变量存储 ==========
class MockVariableStore {
  private variables = new Map<string, { value: unknown; type: string }>();

  set(name: string, value: unknown, type = 'string') {
    this.variables.set(name, { value, type });
  }

  get(name: string): unknown {
    return this.variables.get(name)?.value;
  }

  getAll(): Map<string, { value: unknown; type: string }> {
    return new Map(this.variables);
  }

  resolveReferences(template: string): string {
    return template.replace(/\{\{([^}]+)\}\}/g, (_match, name) => {
      const trimmed = name.trim();
      const found = this.variables.get(trimmed);
      if (found === undefined) return `{{${name}}}`;
      return String(found.value);
    });
  }

  clear() {
    this.variables.clear();
  }
}

// ========== Mock Event Bus ==========
type EventHandler = (event: ECM) => void;

class MockEventBus {
  private handlers: EventHandler[] = [];
  private events: { timestamp: number; topic: string; data: ECM }[] = [];

  subscribe(handler: EventHandler) {
    this.handlers.push(handler);
  }

  unsubscribe(handler: EventHandler) {
    this.handlers = this.handlers.filter(h => h !== handler);
  }

  publish(topic: string, msg: ECM) {
    const record = { timestamp: Date.now() / 1000, topic, data: msg };
    this.events.push(record);
    this.handlers.forEach(h => {
      try { h(msg); } catch { /* ignore */ }
    });
  }

  getHistory() { return [...this.events]; }
  clearHistory() { this.events = []; }
}

// ========== Mock Blackboard ==========
class MockBlackboard {
  private store = new Map<string, { value: unknown; readBy: string[]; writeBy: string[] }>();
  private auditLog: AuditEntry[] = [];

  get(key: string, agentId: string): unknown {
    const entry = this.store.get(key);
    if (!entry) return null;
    entry.readBy.push(agentId);
    this.auditLog.push({ action: 'get', agent: agentId, key, timestamp: Date.now() / 1000 });
    return entry.value;
  }

  put(key: string, value: unknown, agentId: string) {
    const existing = this.store.get(key);
    const entry = {
      value,
      readBy: existing?.readBy ?? [],
      writeBy: [...(existing?.writeBy ?? []), agentId],
    };
    this.store.set(key, entry);
    this.auditLog.push({ action: 'put', agent: agentId, key, timestamp: Date.now() / 1000 });
  }

  getKeys(): { key: string; type: string; size: number }[] {
    return Array.from(this.store.entries()).map(([key, entry]) => ({
      key,
      type: typeof entry.value,
      size: JSON.stringify(entry.value).length,
    }));
  }

  getPermissions(key: string): { readers: string[]; writers: string[] } | null {
    const entry = this.store.get(key);
    if (!entry) return null;
    return { readers: entry.readBy, writers: entry.writeBy };
  }

  getAuditLog(): AuditEntry[] { return [...this.auditLog]; }
}

// ========== Mock Worker ==========
class MockWorker {
  agentId: string;
  displayName: string;
  description: string;
  icon: string;
  skills: string[];
  state: Capability['state'];
  load: number;
  weight: number;
  taskHandler: string;
  modelConfig?: Capability['model_config'];
  readKeys: string[];
  writeKeys: string[];
  pendingTasks: number;
  loadHistory: { time: number; load: number }[];
  recentTasks: Capability['recent_tasks'];
  lastHeartbeat: number;
  private failProbability: number;
  private delayRange: [number, number];

  constructor(agentId: string, skills: string[], failProb = 0.1, delayRange: [number, number] = [200, 800]) {
    this.agentId = agentId;
    this.displayName = agentId;
    this.description = '';
    this.icon = '';
    this.skills = skills;
    this.state = 'running';
    this.load = 0;
    this.weight = 1;
    this.taskHandler = '';
    this.readKeys = [];
    this.writeKeys = [];
    this.pendingTasks = 0;
    this.loadHistory = [];
    this.recentTasks = [];
    this.lastHeartbeat = Date.now() / 1000;
    this.failProbability = failProb;
    this.delayRange = delayRange;
  }

  async execute(ecm: ECM): Promise<{ success: boolean; result?: unknown }> {
    this.load++;
    this.loadHistory.push({ time: Date.now() / 1000, load: this.load });
    const startTime = Date.now();
    const delay = this.delayRange[0] + Math.random() * (this.delayRange[1] - this.delayRange[0]);
    await new Promise(resolve => setTimeout(resolve, delay));
    this.load--;
    this.loadHistory.push({ time: Date.now() / 1000, load: this.load });
    const duration = (Date.now() - startTime) / 1000;

    if (Math.random() < this.failProbability) {
      this.recentTasks.push({ timestamp: Date.now() / 1000, intent_id: ecm.intent_id, status: 'failed', duration });
      return { success: false, result: 'Simulated failure' };
    }

    this.recentTasks.push({ timestamp: Date.now() / 1000, intent_id: ecm.intent_id, status: 'success', duration });

    // Handle code execution nodes
    const code = ecm.payload?.code as string | undefined;
    if (code && this.taskHandler === 'universal_executor') {
      try {
        // Safe code execution in mock mode - just evaluate simple expressions
        const fn = new Function('input', 'deps', 'blackboard', `return (${code})`);
        const result = fn(
          ecm.payload?.input || {},
          ecm.payload?.deps || {},
          ecm.payload?.blackboard || {}
        );
        return { success: true, result: { output: result, code_executed: true } };
      } catch (err) {
        return { success: true, result: { output: null, error: (err as Error).message, code_executed: true } };
      }
    }

    const result = {
      node_name: ecm.intent,
      output: `Mock result for ${ecm.intent} by ${this.agentId}`,
      timestamp: Date.now() / 1000,
    };
    return { success: true, result };
  }

  getCapability(): Capability {
    return {
      agent_id: this.agentId,
      display_name: this.displayName,
      description: this.description,
      icon: this.icon,
      skills: this.skills,
      load: this.load,
      history: [],
      load_history: this.loadHistory.slice(-60),
      recent_tasks: this.recentTasks.slice(-20),
      read_keys: this.readKeys,
      write_keys: this.writeKeys,
      state: this.state,
      weight: this.weight,
      pending_tasks: this.pendingTasks,
      task_handler: this.taskHandler,
      last_heartbeat: this.lastHeartbeat,
    };
  }
}

// ========== Mock Scheduler ==========
interface MockSchedulerOptions {
  strategy: 'least_loaded' | 'auction';
  auctionTimeout: number;
}

class MockScheduler {
  private workers: MockWorker[] = [];
  private options: MockSchedulerOptions = { strategy: 'least_loaded', auctionTimeout: 5 };
  private bus: MockEventBus;

  constructor(bus: MockEventBus) { this.bus = bus; }

  setOptions(opts: Partial<MockSchedulerOptions>) { Object.assign(this.options, opts); }
  getOptions() { return { ...this.options }; }

  registerWorker(worker: MockWorker) { this.workers.push(worker); }
  unregisterWorker(agentId: string) { this.workers = this.workers.filter(w => w.agentId !== agentId); }

  getWorkers(): MockWorker[] { return [...this.workers]; }

  async schedule(ecm: ECM): Promise<{ success: boolean; result?: unknown }> {
    if (this.options.strategy === 'auction') {
      return this.auctionSchedule(ecm);
    }
    return this.leastLoadedSchedule(ecm);
  }

  private async leastLoadedSchedule(ecm: ECM) {
    const candidates = this.workers
      .filter(w => w.state === 'running' && ecm.required_skills.every(s => w.skills.includes(s)))
      .sort((a, b) => a.load - b.load);

    if (candidates.length === 0) {
      return { success: false, result: 'No available worker' };
    }

    this.bus.publish('task.assigned', ecm);
    const worker = candidates[0];
    const r = await worker.execute(ecm);
    this.bus.publish(r.success ? 'task.completed' : 'task.failed', {
      ...ecm,
      payload: { ...ecm.payload, result: r.result },
    });
    return r;
  }

  private async auctionSchedule(ecm: ECM) {
    this.bus.publish('task.auction', ecm);
    await new Promise(r => setTimeout(r, 100)); // 模拟拍卖等待
    return this.leastLoadedSchedule(ecm);
  }
}

// ========== Mock Orchestrator ==========
class MockOrchestrator {
  private scheduler: MockScheduler;
  private bus: MockEventBus;
  private blackboard: MockBlackboard;
  private variableStore: MockVariableStore;
  private logCollector: MockLogCollector;

  constructor(scheduler: MockScheduler, bus: MockEventBus, blackboard: MockBlackboard, variableStore: MockVariableStore, logCollector: MockLogCollector) {
    this.scheduler = scheduler;
    this.bus = bus;
    this.blackboard = blackboard;
    this.variableStore = variableStore;
    this.logCollector = logCollector;
  }

  private publishNodeStatus(nodeName: string, status: string, result?: unknown) {
    this.bus.publish('node.status', {
      trace_id: `trace-${Date.now()}-${nodeName}`,
      intent: nodeName,
      intent_id: `intent-${nodeName}`,
      emitter: 'orchestrator',
      payload: {},
      reply_to: '',
      timestamp: Date.now() / 1000,
      required_skills: [],
      priority: 'normal',
      metadata: { status, result },
    });
  }

  /** 评估条件分支 */
  private evaluateCondition(condition: string, context: Record<string, unknown>): boolean {
    try {
      // 替换 {{variable}} 语法
      const resolved = this.variableStore.resolveReferences(condition);
      // 安全评估 JS 表达式
      const fn = new Function('context', `return (${resolved})`);
      return !!fn(context);
    } catch {
      return false;
    }
  }

  /** 执行条件分支节点 */
  private async executeConditionNode(
    nodeName: string,
    def: TaskGraph[string],
    results: Record<string, unknown>,
    completed: Set<string>,
    nodeStatus: Map<string, 'pending' | 'running' | 'completed' | 'failed'>,
    _nodeNames: string[]
  ) {
    this.logCollector.addLog({
      workflow_id: 'mock',
      node_id: nodeName,
      level: 'info',
      message: `执行条件分支节点: ${nodeName}`,
      timestamp: Date.now(),
    });

    // 获取条件配置
    const conditionData = (def as unknown as { condition_data?: ConditionNodeData }).condition_data;
    if (!conditionData || !conditionData.branches || conditionData.branches.length === 0) {
      this.logCollector.addLog({
        workflow_id: 'mock',
        node_id: nodeName,
        level: 'warn',
        message: `条件节点 ${nodeName} 没有配置分支`,
        timestamp: Date.now(),
      });
      nodeStatus.set(nodeName, 'completed');
      completed.add(nodeName);
      results[nodeName] = { branch: 'default' };
      this.publishNodeStatus(nodeName, 'completed', results[nodeName]);
      return;
    }

    // 构建执行上下文
    const context: Record<string, unknown> = {};
    for (const dep of def.depends_on) {
      if (results[dep] !== undefined) {
        context[dep] = results[dep];
      }
    }

    // 评估每个分支
    let matchedBranch = conditionData.default_branch || 'default';
    for (const branch of conditionData.branches) {
      if (branch.condition && this.evaluateCondition(branch.condition, context)) {
        matchedBranch = branch.id;
        break;
      }
    }

    this.logCollector.addLog({
      workflow_id: 'mock',
      node_id: nodeName,
      level: 'info',
      message: `条件分支匹配: ${matchedBranch}`,
      timestamp: Date.now(),
      data: { matched_branch: matchedBranch },
    });

    nodeStatus.set(nodeName, 'completed');
    completed.add(nodeName);
    results[nodeName] = { branch: matchedBranch, context };

    this.bus.publish('node.completed', {
      trace_id: `trace-${Date.now()}-${nodeName}`,
      intent: nodeName,
      intent_id: `intent-${nodeName}`,
      emitter: 'orchestrator',
      payload: { branch: matchedBranch },
      reply_to: '',
      timestamp: Date.now() / 1000,
      required_skills: [],
      priority: 'normal',
      metadata: { status: 'completed', result: results[nodeName] },
    });
    this.publishNodeStatus(nodeName, 'completed', results[nodeName]);
  }

  async execute(graph: TaskGraph): Promise<Record<string, unknown>> {
    const results: Record<string, unknown> = {};
    const nodeNames = Object.keys(graph);

    // 拓扑排序
    const inDegree = new Map<string, number>();
    const adjacency = new Map<string, string[]>();

    nodeNames.forEach(n => {
      inDegree.set(n, graph[n].depends_on.length);
      adjacency.set(n, []);
    });
    nodeNames.forEach(n => {
      graph[n].depends_on.forEach(d => {
        adjacency.get(d)?.push(n);
      });
    });

    const completed = new Set<string>();
    const nodeStatus = new Map<string, 'pending' | 'running' | 'completed' | 'failed'>();

    // 初始化状态
    nodeNames.forEach(n => nodeStatus.set(n, 'pending'));

    this.logCollector.addLog({
      workflow_id: 'mock',
      level: 'info',
      message: `开始执行工作流，共 ${nodeNames.length} 个节点`,
      timestamp: Date.now(),
    });

    while (completed.size < nodeNames.length) {
      const ready: string[] = [];

      // 找到所有就绪的节点
      nodeNames.forEach(n => {
        if (nodeStatus.get(n) !== 'pending') return;
        const depsDone = graph[n].depends_on.every(d => completed.has(d));
        if (depsDone) ready.push(n);
      });

      if (ready.length === 0) {
        // 检查是否有失败导致死锁
        const hasRunning = nodeNames.some(n => nodeStatus.get(n) === 'running');
        if (!hasRunning) break;
        await new Promise(r => setTimeout(r, 50));
        continue;
      }

      // 并行执行就绪节点
      const tasks = ready.map(async (nodeName) => {
        nodeStatus.set(nodeName, 'running');
        this.publishNodeStatus(nodeName, 'running');
        const def = graph[nodeName];
        const variant = (def as TaskNodeDef & { variant?: string }).variant;

        if (variant === 'hitl') {
          this.logCollector.addLog({
            workflow_id: 'mock',
            node_id: nodeName,
            level: 'info',
            message: `HITL 节点 ${nodeName}：模拟自动批准`,
            timestamp: Date.now(),
          });
          await new Promise((r) => setTimeout(r, 400));
          results[nodeName] = { status: 'approved', mock_hitl: true };
          nodeStatus.set(nodeName, 'completed');
          completed.add(nodeName);
          this.publishNodeStatus(nodeName, 'completed', results[nodeName]);
          return;
        }

        // 检查是否为条件分支节点
        const nodeType = (def as unknown as { node_type?: string }).node_type;
        if (nodeType === 'condition' || (def as unknown as { condition_data?: unknown }).condition_data) {
          await this.executeConditionNode(nodeName, def, results, completed, nodeStatus, nodeNames);
          return;
        }

        const ecm: ECM = {
          trace_id: `trace-${Date.now()}-${nodeName}`,
          intent: nodeName,
          intent_id: `intent-${nodeName}`,
          emitter: 'orchestrator',
          expectation: def.expectation,
          payload: {},
          reply_to: '',
          timestamp: Date.now() / 1000,
          required_skills: def.required_skills ?? [],
          priority: 'normal',
          metadata: {},
        };

        this.bus.publish('intent.created', ecm);
        this.logCollector.addLog({
          workflow_id: 'mock',
          node_id: nodeName,
          level: 'debug',
          message: `节点 ${nodeName} 开始执行`,
          timestamp: Date.now(),
        });

        // 模拟重试
        const maxAttempts = def.retry_policy?.max_attempts ?? 1;
        let success = false;
        let result: unknown = null;
        let error: string | undefined;

        for (let attempt = 0; attempt < maxAttempts; attempt++) {
          if (attempt > 0) {
            const delay = def.retry_policy?.backoff_type === 'exponential'
              ? Math.min((def.retry_policy.backoff_base ?? 1) * Math.pow(2, attempt - 1) * 1000, (def.retry_policy?.max_backoff ?? 30) * 1000)
              : (def.retry_policy?.backoff_base ?? 1) * 1000;
            await new Promise(r => setTimeout(r, delay));
          }

          const r = await this.scheduler.schedule(ecm);
          if (r.success) {
            success = true;
            result = r.result;
            break;
          }
          error = (r.result as string) ?? 'Unknown error';
          this.logCollector.addLog({
            workflow_id: 'mock',
            node_id: nodeName,
            level: 'warn',
            message: `节点 ${nodeName} 第 ${attempt + 1} 次尝试失败: ${error}`,
            timestamp: Date.now(),
          });
        }

        // 失败处理
        if (!success) {
          if (def.on_failure === 'abort') {
            nodeStatus.set(nodeName, 'failed');
            ecm.metadata = { status: 'failed', result: error };
            this.bus.publish('node.failed', ecm);
            this.publishNodeStatus(nodeName, 'failed', error);
            this.logCollector.addLog({
              workflow_id: 'mock',
              node_id: nodeName,
              level: 'error',
              message: `节点 ${nodeName} 执行失败: ${error}`,
              timestamp: Date.now(),
            });
            throw new Error(`Node ${nodeName} failed: ${error}`);
          }
          // 'skip' - 标记完成但记录错误
          results[nodeName] = { error, skipped: true };
          this.logCollector.addLog({
            workflow_id: 'mock',
            node_id: nodeName,
            level: 'warn',
            message: `节点 ${nodeName} 已跳过`,
            timestamp: Date.now(),
          });
        } else {
          results[nodeName] = result;
          // 如果定义了 state_key，写入黑板
          if (def.expectation?.state_key) {
            this.blackboard.put(def.expectation.state_key, result, 'orchestrator');
          }
        }

        nodeStatus.set(nodeName, 'completed');
        completed.add(nodeName);
        ecm.metadata = { status: 'completed', result: results[nodeName] };
        this.bus.publish('node.completed', ecm);
        this.publishNodeStatus(nodeName, 'completed', results[nodeName]);
        this.logCollector.addLog({
          workflow_id: 'mock',
          node_id: nodeName,
          level: 'info',
          message: `节点 ${nodeName} 执行完成`,
          timestamp: Date.now(),
        });
      });

      await Promise.all(tasks);
    }

    this.logCollector.addLog({
      workflow_id: 'mock',
      level: 'info',
      message: `工作流执行完成，共 ${completed.size} 个节点`,
      timestamp: Date.now(),
    });

    return results;
  }

  getLogs(): ExecutionLog[] {
    return this.logCollector.getLogs();
  }

  clearLogs() {
    this.logCollector.clearLogs();
  }
}

// ========== Mock Knowledge Base ==========
interface MockDocument {
  id: string;
  name: string;
  content: string;
  chunks: string[];
  embedded: boolean;
}

interface MockKnowledgeBase {
  id: string;
  name: string;
  description: string;
  embedding_model: string;
  chunk_size: number;
  chunk_overlap: number;
  documents: MockDocument[];
  created_at: number;
  updated_at: number;
}

class MockKnowledgeBaseStore {
  private knowledgeBases = new Map<string, MockKnowledgeBase>();

  create(data: { name: string; description?: string; embedding_model?: string; chunk_size?: number; chunk_overlap?: number }): MockKnowledgeBase {
    const kb: MockKnowledgeBase = {
      id: `kb_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      name: data.name,
      description: data.description || '',
      embedding_model: data.embedding_model || 'text-embedding-ada-002',
      chunk_size: data.chunk_size || 512,
      chunk_overlap: data.chunk_overlap || 50,
      documents: [],
      created_at: Date.now(),
      updated_at: Date.now(),
    };
    this.knowledgeBases.set(kb.id, kb);
    return kb;
  }

  getAll(): MockKnowledgeBase[] {
    return Array.from(this.knowledgeBases.values());
  }

  get(id: string): MockKnowledgeBase | undefined {
    return this.knowledgeBases.get(id);
  }

  update(id: string, updates: Partial<MockKnowledgeBase>): void {
    const kb = this.knowledgeBases.get(id);
    if (kb) {
      Object.assign(kb, updates);
      kb.updated_at = Date.now();
    }
  }

  delete(id: string): void {
    this.knowledgeBases.delete(id);
  }

  addDocument(kbId: string, doc: { name: string; content: string }): MockDocument | null {
    const kb = this.knowledgeBases.get(kbId);
    if (!kb) return null;

    // Simulate chunking
    const words = doc.content.split(/\s+/);
    const chunks: string[] = [];
    const step = kb.chunk_size - kb.chunk_overlap;
    for (let i = 0; i < words.length; i += step) {
      chunks.push(words.slice(i, i + kb.chunk_size).join(' '));
    }

    const newDoc: MockDocument = {
      id: `doc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      name: doc.name,
      content: doc.content,
      chunks: chunks.length > 0 ? chunks : [doc.content],
      embedded: false,
    };

    kb.documents.push(newDoc);
    kb.updated_at = Date.now();
    return newDoc;
  }

  embedDocument(kbId: string, docId: string): void {
    const kb = this.knowledgeBases.get(kbId);
    if (!kb) return;
    const doc = kb.documents.find((d) => d.id === docId);
    if (doc) doc.embedded = true;
  }

  search(kbId: string, query: string): { document: string; score: number; chunk: string }[] {
    const kb = this.knowledgeBases.get(kbId);
    if (!kb) return [];

    const results: { document: string; score: number; chunk: string }[] = [];
    const queryLower = query.toLowerCase();

    for (const doc of kb.documents) {
      if (!doc.embedded) continue;
      for (const chunk of doc.chunks) {
        // Simple keyword matching as mock vector search
        const chunkLower = chunk.toLowerCase();
        let score = 0;
        for (const word of queryLower.split(/\s+/)) {
          if (word.length > 2 && chunkLower.includes(word)) {
            score += 0.2;
          }
        }
        if (score > 0) {
          results.push({ document: doc.name, score: Math.min(score, 1), chunk });
        }
      }
    }

    return results.sort((a, b) => b.score - a.score).slice(0, 10);
  }
}

// ========== Mock Analytics Store ==========
interface ExecutionRecord {
  id: string;
  workflow_id: string;
  status: 'success' | 'failed' | 'timeout';
  duration: number;
  timestamp: number;
  node_durations: { node_name: string; duration: number }[];
  error_type?: string;
}

class MockAnalyticsStore {
  private executions: ExecutionRecord[] = [];

  recordExecution(record: Omit<ExecutionRecord, 'id'>): void {
    this.executions.push({
      ...record,
      id: `exec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    });
  }

  getExecutions(days?: number): ExecutionRecord[] {
    if (!days) return [...this.executions];
    const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
    return this.executions.filter((e) => e.timestamp >= cutoff);
  }

  getSummary(days = 7): {
    total_executions: number;
    success_count: number;
    failed_count: number;
    success_rate: number;
    avg_duration: number;
  } {
    const records = this.getExecutions(days);
    const total = records.length;
    const success = records.filter((r) => r.status === 'success').length;
    const failed = records.filter((r) => r.status !== 'success').length;
    const avgDuration = total > 0 ? records.reduce((s, r) => s + r.duration, 0) / total : 0;

    return {
      total_executions: total,
      success_count: success,
      failed_count: failed,
      success_rate: total > 0 ? (success / total) * 100 : 0,
      avg_duration: avgDuration,
    };
  }

  getNodeRankings(days = 7): { node_name: string; avg_duration: number; max_duration: number; min_duration: number; call_count: number }[] {
    const records = this.getExecutions(days);
    const nodeStats = new Map<string, number[]>();

    for (const record of records) {
      for (const nd of record.node_durations) {
        const durations = nodeStats.get(nd.node_name) || [];
        durations.push(nd.duration);
        nodeStats.set(nd.node_name, durations);
      }
    }

    return Array.from(nodeStats.entries())
      .map(([name, durations]) => ({
        node_name: name,
        avg_duration: durations.reduce((s, d) => s + d, 0) / durations.length,
        max_duration: Math.max(...durations),
        min_duration: Math.min(...durations),
        call_count: durations.length,
      }))
      .sort((a, b) => b.avg_duration - a.avg_duration);
  }

  getErrorStats(days = 7): { error_type: string; count: number; percentage: number }[] {
    const records = this.getExecutions(days);
    const failedRecords = records.filter((r) => r.status !== 'success');
    const total = failedRecords.length;
    if (total === 0) return [];

    const errorCounts = new Map<string, number>();
    for (const record of failedRecords) {
      const errorType = record.error_type || 'Unknown';
      errorCounts.set(errorType, (errorCounts.get(errorType) || 0) + 1);
    }

    return Array.from(errorCounts.entries())
      .map(([type, count]) => ({
        error_type: type,
        count,
        percentage: (count / total) * 100,
      }))
      .sort((a, b) => b.count - a.count);
  }

  clear(): void {
    this.executions = [];
  }
}

// ========== Mock Engine (主入口) ==========
export interface IEngine {
  executeWorkflow(graph: TaskGraph, onNodeStatus?: (node: string, status: string, result?: unknown) => void): Promise<Record<string, unknown>>;
  registerAgent(cap: Capability): void;
  unregisterAgent(id: string): void;
  drainAgent(id: string): void;
  getAgents(): Capability[];
  getBlackboardKeys(): { key: string; type: string; size: number }[];
  getBlackboardValue(key: string): unknown;
  setBlackboardValue(key: string, value: unknown): void;
  getBlackboardPermissions(key: string): { readers: string[]; writers: string[] } | null;
  getAuditLog(): AuditEntry[];
  getMetrics(): MetricsSnapshot;
  getEventHistory(): { timestamp: number; topic: string; data: ECM }[];
  clearEvents(): void;
  onEvent(handler: (event: ECM) => void): void;
  offEvent(handler: (event: ECM) => void): void;
  getConfig(): { strategy: string; auctionTimeout: number; failProbability: number; delayRange: [number, number] };
  setConfig(opts: { strategy?: string; auctionTimeout?: number; failProbability?: number; delayRange?: [number, number] }): void;
  getLogs(): ExecutionLog[];
  clearLogs(): void;
  setVariable(name: string, value: unknown): void;
  getVariable(name: string): unknown;
  // Knowledge Base
  createKnowledgeBase(data: { name: string; description?: string; embedding_model?: string }): { id: string };
  getKnowledgeBases(): { id: string; name: string; document_count: number }[];
  deleteKnowledgeBase(id: string): void;
  addDocumentToKB(kbId: string, name: string, content: string): { id: string } | null;
  searchKB(kbId: string, query: string): { document: string; score: number; chunk: string }[];
  // Analytics
  getAnalyticsSummary(days?: number): ReturnType<MockAnalyticsStore['getSummary']>;
  getNodeRankings(days?: number): ReturnType<MockAnalyticsStore['getNodeRankings']>;
  getErrorStats(days?: number): ReturnType<MockAnalyticsStore['getErrorStats']>;
}

export class MockEngine implements IEngine {
  private bus: MockEventBus;
  private scheduler: MockScheduler;
  private blackboard: MockBlackboard;
  private variableStore: MockVariableStore;
  private logCollector: MockLogCollector;
  private orchestrator: MockOrchestrator;
  private kbStore: MockKnowledgeBaseStore;
  private analyticsStore: MockAnalyticsStore;
  private failProbability = 0.1;
  private delayRange: [number, number] = [200, 800];

  constructor() {
    this.bus = new MockEventBus();
    this.blackboard = new MockBlackboard();
    this.variableStore = new MockVariableStore();
    this.logCollector = new MockLogCollector();
    this.kbStore = new MockKnowledgeBaseStore();
    this.analyticsStore = new MockAnalyticsStore();
    this.scheduler = new MockScheduler(this.bus);
    this.orchestrator = new MockOrchestrator(this.scheduler, this.bus, this.blackboard, this.variableStore, this.logCollector);

    // 注册一些默认 Agent
    // 通用 Agent — 覆盖常见模板所需的所有技能
    this.registerAgent({
      agent_id: 'agent-universal',
      display_name: '通用执行引擎',
      description: '覆盖所有常见技能，支持模板开箱即用',
      icon: '🚀',
      skills: [
        'search', 'embedding', 'ranking', 'llm', 'summarization',
        'nlp', 'text_analysis',
        'planning', 'analysis', 'reasoning', 'decomposition',
        'crawling', 'data_processing', 'data_analysis', 'preprocessing',
        'ml', 'training',
        'testing', 'evaluation', 'decision',
        'visualization', 'reporting',
        'image_processing', 'ocr', 'classification',
      ],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'universal_executor',
      last_heartbeat: Date.now() / 1000,
    });
    // 专用 Agent — 保留原有的专用角色
    this.registerAgent({
      agent_id: 'agent-alpha',
      display_name: 'NLP 分析助手',
      description: '负责自然语言处理和文本分析',
      icon: '🤖',
      skills: ['nlp', 'text_analysis', 'summarization'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'nlp_processor',
      last_heartbeat: Date.now() / 1000,
    });
    this.registerAgent({
      agent_id: 'agent-beta',
      display_name: '图像处理专家',
      description: '负责图像识别和OCR处理',
      icon: '👁️',
      skills: ['image_processing', 'ocr', 'classification'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'image_processor',
      last_heartbeat: Date.now() / 1000,
    });
    this.registerAgent({
      agent_id: 'agent-gamma',
      display_name: '数据分析引擎',
      description: '负责数据分析和可视化报告生成',
      icon: '📊',
      skills: ['data_analysis', 'visualization', 'reporting'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'data_analyzer',
      last_heartbeat: Date.now() / 1000,
    });

    // 搜索与信息获取 Agent
    this.registerAgent({
      agent_id: 'agent-search',
      display_name: '搜索引擎助手',
      description: '负责网络搜索、网页抓取和信息提取',
      icon: '🔍',
      skills: ['search', 'web', 'retrieval', 'crawling', 'scraping'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'search_worker',
      last_heartbeat: Date.now() / 1000,
    });

    // NLP 与文本处理 Agent
    this.registerAgent({
      agent_id: 'agent-nlp',
      display_name: 'NLP 文本处理引擎',
      description: '负责情感分析、文本摘要、翻译和关键词提取',
      icon: '📝',
      skills: ['nlp', 'text_analysis', 'summarization', 'translation', 'sentiment', 'extraction', 'chatbot'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'nlp_worker',
      last_heartbeat: Date.now() / 1000,
    });

    // 视觉与图像 Agent
    this.registerAgent({
      agent_id: 'agent-vision',
      display_name: '计算机视觉引擎',
      description: '负责图像识别、目标检测、人脸识别和图像生成',
      icon: '👁️',
      skills: ['image_processing', 'ocr', 'classification', 'object_detection', 'face_recognition', 'image_generation', 'video_analysis'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'vision_worker',
      last_heartbeat: Date.now() / 1000,
    });

    // 数据分析 Agent
    this.registerAgent({
      agent_id: 'agent-data',
      display_name: '数据科学引擎',
      description: '负责数据统计、特征工程、预测分析和可视化',
      icon: '📈',
      skills: ['data_analysis', 'visualization', 'reporting', 'data_processing', 'preprocessing', 'feature_engineering', 'forecasting', 'statistics'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'data_worker',
      last_heartbeat: Date.now() / 1000,
    });

    // AI 推理与规划 Agent
    this.registerAgent({
      agent_id: 'agent-reason',
      display_name: '推理与规划引擎',
      description: '负责逻辑推理、任务规划、决策制定和问题解决',
      icon: '🧠',
      skills: ['llm', 'reasoning', 'decision', 'planning', 'decomposition', 'analysis', 'thinking', 'problem_solving'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'reasoning_worker',
      last_heartbeat: Date.now() / 1000,
    });

    // 安全与合规 Agent
    this.registerAgent({
      agent_id: 'agent-security',
      display_name: '安全防护引擎',
      description: '负责安全审计、漏洞扫描、威胁检测和合规检查',
      icon: '🔐',
      skills: ['security', 'audit', 'vulnerability_scan', 'threat_detection', 'compliance', 'encryption'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'security_worker',
      last_heartbeat: Date.now() / 1000,
    });

    // 开发与工程 Agent
    this.registerAgent({
      agent_id: 'agent-dev',
      display_name: '开发工程引擎',
      description: '负责代码生成、代码审查、测试和文档生成',
      icon: '💻',
      skills: ['code_generation', 'code_review', 'testing', 'evaluation', 'debugging', 'documentation', 'deployment'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'dev_worker',
      last_heartbeat: Date.now() / 1000,
    });

    // ML 与训练 Agent
    this.registerAgent({
      agent_id: 'agent-ml',
      display_name: '机器学习引擎',
      description: '负责模型训练、微调、评估和强化学习',
      icon: '🔬',
      skills: ['ml', 'training', 'embedding', 'ranking', 'fine_tuning', 'model_evaluation', 'reinforcement_learning'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'ml_worker',
      last_heartbeat: Date.now() / 1000,
    });

    // 集成与通信 Agent
    this.registerAgent({
      agent_id: 'agent-integration',
      display_name: '集成通信引擎',
      description: '负责 API 集成、通知推送、Webhook 和外部服务调用',
      icon: '🌐',
      skills: ['api', 'integration', 'notification', 'webhook'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'integration_worker',
      last_heartbeat: Date.now() / 1000,
    });

    // 工具与自动化 Agent
    this.registerAgent({
      agent_id: 'agent-automation',
      display_name: '自动化工具引擎',
      description: '负责文件操作、数据库访问、工作流编排和定时调度',
      icon: '🔧',
      skills: ['file_io', 'database', 'workflow', 'automation', 'scheduling', 'monitoring'],
      load: 0, history: [], load_history: [], recent_tasks: [],
      read_keys: [], write_keys: [],
      state: 'running', weight: 1, pending_tasks: 0,
      task_handler: 'automation_worker',
      last_heartbeat: Date.now() / 1000,
    });
  }

  async executeWorkflow(
    graph: TaskGraph,
    onNodeStatus?: (node: string, status: string, result?: unknown) => void
  ): Promise<Record<string, unknown>> {
    // 监听事件以回调节点状态
    const handler = (ecm: ECM) => {
      if (ecm.intent && onNodeStatus) {
        const status = ecm.metadata?.status as string | undefined;
        if (status) {
          onNodeStatus(ecm.intent, status, ecm.metadata?.result);
        }
      }
    };
    this.bus.subscribe(handler);

    try {
      const results = await this.orchestrator.execute(graph);
      return results;
    } finally {
      this.bus.unsubscribe(handler);
    }
  }

  registerAgent(cap: Capability) {
    const w = new MockWorker(cap.agent_id, cap.skills, this.failProbability, this.delayRange);
    w.displayName = cap.display_name || cap.agent_id;
    w.description = cap.description || '';
    w.icon = cap.icon || '';
    w.weight = cap.weight;
    w.taskHandler = cap.task_handler || '';
    w.readKeys = cap.read_keys || [];
    w.writeKeys = cap.write_keys || [];
    if (cap.model_config) w.modelConfig = cap.model_config;
    this.scheduler.registerWorker(w);
  }

  unregisterAgent(id: string) { this.scheduler.unregisterWorker(id); }
  drainAgent(id: string) {
    const workers = this.scheduler.getWorkers();
    const w = workers.find(x => x.agentId === id);
    if (w) w.state = 'draining';
  }

  getAgents(): Capability[] {
    return this.scheduler.getWorkers().map(w => w.getCapability());
  }

  getBlackboardKeys() { return this.blackboard.getKeys(); }
  getBlackboardValue(key: string) { return this.blackboard.get(key, 'ui'); }
  setBlackboardValue(key: string, value: unknown) { this.blackboard.put(key, value, 'ui'); }
  getBlackboardPermissions(key: string) { return this.blackboard.getPermissions(key); }
  getAuditLog() { return this.blackboard.getAuditLog(); }

  getMetrics(): MetricsSnapshot {
    const agents = this.getAgents();
    return {
      counters: {
        total_intents: this.bus.getHistory().filter(e => e.topic === 'intent.created').length,
        completed_intents: this.bus.getHistory().filter(e => e.topic === 'task.completed').length,
        failed_intents: this.bus.getHistory().filter(e => e.topic === 'task.failed').length,
      },
      gauges: {
        active_agents: agents.filter(a => a.state === 'running').length,
        total_load: agents.reduce((s, a) => s + a.load, 0),
      },
    };
  }

  getEventHistory() { return this.bus.getHistory(); }
  clearEvents() { this.bus.clearHistory(); }
  onEvent(handler: (event: ECM) => void) { this.bus.subscribe(handler); }
  offEvent(handler: (event: ECM) => void) { this.bus.unsubscribe(handler); }

  getConfig() {
    const opts = this.scheduler.getOptions();
    return {
      strategy: opts.strategy,
      auctionTimeout: opts.auctionTimeout,
      failProbability: this.failProbability,
      delayRange: [...this.delayRange] as [number, number],
    };
  }

  setConfig(opts: { strategy?: string; auctionTimeout?: number; failProbability?: number; delayRange?: [number, number] }) {
    if (opts.strategy) this.scheduler.setOptions({ strategy: opts.strategy as 'least_loaded' | 'auction' });
    if (opts.auctionTimeout !== undefined) this.scheduler.setOptions({ auctionTimeout: opts.auctionTimeout });
    if (opts.failProbability !== undefined) this.failProbability = opts.failProbability;
    if (opts.delayRange) this.delayRange = opts.delayRange;
  }

  getLogs(): ExecutionLog[] {
    return this.orchestrator.getLogs();
  }

  clearLogs(): void {
    this.orchestrator.clearLogs();
  }

  setVariable(name: string, value: unknown): void {
    this.variableStore.set(name, value);
  }

  getVariable(name: string): unknown {
    return this.variableStore.get(name);
  }

  // ========== Knowledge Base Methods ==========
  createKnowledgeBase(data: { name: string; description?: string; embedding_model?: string }): { id: string } {
    const kb = this.kbStore.create(data);
    return { id: kb.id };
  }

  getKnowledgeBases(): { id: string; name: string; document_count: number }[] {
    return this.kbStore.getAll().map((kb) => ({
      id: kb.id,
      name: kb.name,
      document_count: kb.documents.length,
    }));
  }

  deleteKnowledgeBase(id: string): void {
    this.kbStore.delete(id);
  }

  addDocumentToKB(kbId: string, name: string, content: string): { id: string } | null {
    const doc = this.kbStore.addDocument(kbId, { name, content });
    return doc ? { id: doc.id } : null;
  }

  searchKB(kbId: string, query: string): { document: string; score: number; chunk: string }[] {
    return this.kbStore.search(kbId, query);
  }

  // ========== Analytics Methods ==========
  getAnalyticsSummary(days?: number): ReturnType<MockAnalyticsStore['getSummary']> {
    return this.analyticsStore.getSummary(days);
  }

  getNodeRankings(days?: number): ReturnType<MockAnalyticsStore['getNodeRankings']> {
    return this.analyticsStore.getNodeRankings(days);
  }

  getErrorStats(days?: number): ReturnType<MockAnalyticsStore['getErrorStats']> {
    return this.analyticsStore.getErrorStats(days);
  }
}