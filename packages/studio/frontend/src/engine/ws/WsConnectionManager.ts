import type { ECM, Capability, MetricsSnapshot } from '@/types';
import { API_BASE_URL } from '@/utils/api';

// 将 HTTP URL 转为 WebSocket URL
function httpToWs(url: string): string {
  return url.replace('http://', 'ws://').replace('https://', 'wss://');
}

// ========== 事件类型定义 ==========
export type WsEventType =
  | 'subscribed'
  | 'pong'
  | 'engine.info'
  | 'engine.stopped'
  | 'event'
  | 'workflow.status'
  | 'workflow.node_update';

export interface WsMessage {
  type: WsEventType;
  timestamp?: number;
  topics?: string[];
  topic?: string;
  data?: ECM | Record<string, unknown>;
  agents?: Capability[];
  metrics?: MetricsSnapshot;
  wid?: string;
  status?: string;
  node?: string;
}

// ========== 事件回调类型 ==========
export type EventCallback = (topic: string, data: ECM) => void;
export type WorkflowCallback = (nodeName: string, status: string, result?: unknown) => void;
export type MetricsCallback = (metrics: MetricsSnapshot) => void;
export type AgentsCallback = (agents: Capability[]) => void;

// ========== WebSocket 管理器 ==========
class WsConnectionManager {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;

  // 回调注册表
  private eventCallbacks: EventCallback[] = [];
  private workflowCallbacks: WorkflowCallback[] = [];
  private metricsCallbacks: MetricsCallback[] = [];
  private agentsCallbacks: AgentsCallback[] = [];

  private subscribedTopics: Set<string> = new Set();

  constructor(url?: string) {
    this.url = url || `${httpToWs(API_BASE_URL)}/ws`;
  }

  async connect(): Promise<boolean> {
    return new Promise((resolve) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('[WsManager] Connected');
          this.reconnectAttempts = 0;
          this.reconnectDelay = 1000;
          this.resubscribe();
          resolve(true);
        };

        this.ws.onmessage = (event) => {
          try {
            const msg: WsMessage = JSON.parse(event.data);
            this.handleMessage(msg);
          } catch (e) {
            console.error('[WsManager] Parse error:', e);
          }
        };

        this.ws.onclose = () => {
          console.log('[WsManager] Disconnected');
          this.handleReconnect();
        };

        this.ws.onerror = (error) => {
          console.error('[WsManager] Error:', error);
          resolve(false);
        };
      } catch (e) {
        console.error('[WsManager] Connect failed:', e);
        resolve(false);
      }
    });
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.subscribedTopics.clear();
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // 发送消息
  send(msg: Record<string, unknown>) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  // 订阅引擎事件
  subscribeToEngine(topics: string[] = ['task.completed', 'task.failed', 'intent.timeout', 'node.event']) {
    this.send({ type: 'subscribe', topics });
    topics.forEach(t => this.subscribedTopics.add(t));
  }

  // 请求引擎信息
  requestEngineInfo() {
    this.send({ type: 'engine.info' });
  }

  // 停止引擎
  requestEngineStop() {
    this.send({ type: 'engine.stop' });
  }

  // Ping
  ping() {
    this.send({ type: 'ping' });
  }

  // ========== 回调注册 ==========
  onEvent(cb: EventCallback) {
    this.eventCallbacks.push(cb);
    return () => { this.eventCallbacks = this.eventCallbacks.filter(c => c !== cb); };
  }

  onWorkflowStatus(cb: WorkflowCallback) {
    this.workflowCallbacks.push(cb);
    return () => { this.workflowCallbacks = this.workflowCallbacks.filter(c => c !== cb); };
  }

  onMetrics(cb: MetricsCallback) {
    this.metricsCallbacks.push(cb);
    return () => { this.metricsCallbacks = this.metricsCallbacks.filter(c => c !== cb); };
  }

  onAgents(cb: AgentsCallback) {
    this.agentsCallbacks.push(cb);
    return () => { this.agentsCallbacks = this.agentsCallbacks.filter(c => c !== cb); };
  }

  // ========== 消息处理 ==========
  private handleMessage(msg: WsMessage) {
    switch (msg.type) {
      case 'event':
        if (msg.topic && msg.data) {
          const ecm = msg.data as ECM;
          this.eventCallbacks.forEach(cb => cb(msg.topic!, ecm));
        }
        break;

      case 'workflow.status':
        if (msg.node && msg.status) {
          this.workflowCallbacks.forEach(cb => cb(msg.node!, msg.status!));
        }
        break;

      case 'engine.info':
        if (msg.agents) {
          this.agentsCallbacks.forEach(cb => cb(msg.agents as Capability[]));
        }
        if (msg.metrics) {
          this.metricsCallbacks.forEach(cb => cb(msg.metrics as MetricsSnapshot));
        }
        break;

      case 'subscribed':
        console.log('[WsManager] Subscribed to:', msg.topics);
        break;

      case 'engine.stopped':
        console.log('[WsManager] Engine stopped');
        break;

      case 'pong':
        // Ping response, ignore
        break;

      default:
        console.log('[WsManager] Unknown message type:', msg.type);
    }
  }

  // ========== 重连逻辑 ==========
  private handleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('[WsManager] Max reconnect attempts reached');
      return;
    }
    this.reconnectAttempts++;
    console.log(`[WsManager] Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts})`);

    this.reconnectTimer = setTimeout(async () => {
      await this.connect();
    }, this.reconnectDelay);

    // 指数退避
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
  }

  // 重连后重新订阅
  private resubscribe() {
    if (this.subscribedTopics.size > 0) {
      this.subscribeToEngine(Array.from(this.subscribedTopics));
    }
  }
}

// 单例
let wsManagerInstance: WsConnectionManager | null = null;

export function getWsManager(url?: string): WsConnectionManager {
  if (!wsManagerInstance) {
    wsManagerInstance = new WsConnectionManager(url);
  }
  return wsManagerInstance;
}

export function resetWsManager() {
  wsManagerInstance?.disconnect();
  wsManagerInstance = null;
}

export default WsConnectionManager;
