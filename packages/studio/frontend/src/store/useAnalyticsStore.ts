import { create } from 'zustand';
import type { AnalyticsData, AnalyticsSummary, ExecutionTrend, NodeDurationRank, AgentLoadDist, ErrorTypeStat } from '@/types';
import { useEngineStore } from '@/store/useEngineStore';
import { apiFetch } from '@/api';

interface AnalyticsState {
  data: AnalyticsData | null;
  loading: boolean;
  error: string | null;
  timeRange: 7 | 30;

  fetchAnalytics: (timeRange?: 7 | 30) => Promise<void>;
  setTimeRange: (range: 7 | 30) => void;
  reset: () => void;
}

function generateMockAnalytics(timeRange: 7 | 30): AnalyticsData {
  const days = timeRange;
  const now = Date.now();
  const dayMs = 24 * 60 * 60 * 1000;

  const trends: ExecutionTrend[] = Array.from({ length: days }, (_, i) => {
    const date = new Date(now - (days - 1 - i) * dayMs);
    const executions = Math.floor(Math.random() * 50) + 10;
    const successes = Math.floor(executions * (0.7 + Math.random() * 0.25));
    const failures = executions - successes;
    return {
      date: date.toISOString().slice(0, 10),
      executions,
      successes,
      failures,
      avg_duration: Math.floor(Math.random() * 5000) + 500,
    };
  });

  const totalExecutions = trends.reduce((sum, t) => sum + t.executions, 0);
  const successCount = trends.reduce((sum, t) => sum + t.successes, 0);
  const failedCount = trends.reduce((sum, t) => sum + t.failures, 0);
  const totalDuration = trends.reduce((sum, t) => sum + t.avg_duration * t.executions, 0);

  const summary: AnalyticsSummary = {
    total_executions: totalExecutions,
    success_count: successCount,
    failed_count: failedCount,
    success_rate: totalExecutions > 0 ? (successCount / totalExecutions) * 100 : 0,
    avg_duration: totalExecutions > 0 ? Math.round(totalDuration / totalExecutions) : 0,
    total_duration: totalDuration,
  };

  const nodeNames = ['数据预处理', '文本分析', '图像识别', '报告生成', '数据验证', '模型推理', '结果聚合'];
  const node_rankings: NodeDurationRank[] = nodeNames.map((name) => {
    const call_count = Math.floor(Math.random() * 200) + 20;
    const avg_duration = Math.floor(Math.random() * 3000) + 200;
    return {
      node_name: name,
      avg_duration,
      max_duration: avg_duration * (1.5 + Math.random()),
      min_duration: avg_duration * (0.3 + Math.random() * 0.5),
      call_count,
    };
  }).sort((a, b) => b.avg_duration - a.avg_duration);

  const engine = useEngineStore.getState().getEngine();
  const agents = engine.getAgents();
  const agent_load: AgentLoadDist[] = agents.slice(0, 6).map((agent) => ({
    agent_id: agent.agent_id,
    display_name: agent.display_name || agent.agent_id,
    execution_count: Math.floor(Math.random() * 150) + 10,
    avg_load: Math.floor(Math.random() * 80) + 5,
    success_rate: 70 + Math.random() * 28,
  }));

  const errorTypes = [
    { error_type: '超时错误', percentage: 35 },
    { error_type: '连接失败', percentage: 25 },
    { error_type: '响应异常', percentage: 20 },
    { error_type: '资源耗尽', percentage: 12 },
    { error_type: '其他', percentage: 8 },
  ];
  const error_stats: ErrorTypeStat[] = errorTypes.map((e) => ({
    ...e,
    count: Math.floor(failedCount * e.percentage / 100),
  }));

  const recent_executions = Array.from({ length: 10 }, (_, i) => {
    const statuses: Array<'success' | 'failed' | 'timeout'> = ['success', 'success', 'success', 'failed', 'timeout'];
    return {
      id: `exec_${now - i * 60000}`,
      workflow_id: `wf_${Math.floor(Math.random() * 100)}`,
      status: statuses[Math.floor(Math.random() * statuses.length)],
      duration: Math.floor(Math.random() * 8000) + 500,
      timestamp: now - i * 60000,
      node_count: Math.floor(Math.random() * 10) + 2,
    };
  });

  return {
    summary,
    trends,
    node_rankings,
    agent_load,
    error_stats,
    recent_executions,
  };
}

async function fetchRealAnalytics(timeRange: 7 | 30): Promise<AnalyticsData> {
  const days = timeRange;
  const [summaryResp, trendResp, agentsResp, errorsResp, promResp] = await Promise.all([
    apiFetch(`/api/analytics/summary?days=${days}`),
    apiFetch(`/api/analytics/workflows/trend?days=${days}`),
    apiFetch('/api/analytics/agents/performance'),
    apiFetch('/api/analytics/errors'),
    apiFetch('/api/analytics/prometheus'),
  ]);

  const trends: ExecutionTrend[] = (trendResp.trend || []).map((t: Record<string, unknown>) => ({
    date: String(t.date || ''),
    executions: Number(t.executions || 0),
    successes: Number(t.successes || 0),
    failures: Number(t.failures || 0),
    avg_duration: Number(t.avg_duration || 0),
  }));

  const wf = summaryResp.workflows || {};
  const totalExecutions = Number(wf.total_executions || trends.reduce((s, t) => s + t.executions, 0));
  const successRate = Number(wf.success_rate || 0);
  const successCount = trends.reduce((s, t) => s + t.successes, 0);
  const failedCount = trends.reduce((s, t) => s + t.failures, 0);

  const summary: AnalyticsSummary = {
    total_executions: totalExecutions,
    success_count: successCount || Math.round(totalExecutions * successRate / 100),
    failed_count: failedCount || Number(errorsResp.total_errors || 0),
    success_rate: successRate || (totalExecutions > 0 ? (successCount / totalExecutions) * 100 : 0),
    avg_duration: Number(wf.avg_duration || 0),
    total_duration: 0,
  };

  const agent_load: AgentLoadDist[] = (agentsResp.agents || []).map((a: Record<string, unknown>) => ({
    agent_id: String(a.agent_id || ''),
    display_name: String(a.agent_id || ''),
    execution_count: Number(a.pending_tasks || 0) + Number(a.load || 0),
    avg_load: Number(a.load || 0),
    success_rate: a.state === 'running' ? 95 : 80,
  }));

  const errorTypes = errorsResp.error_types || {};
  const totalErrors = Number(errorsResp.total_errors || 0);
  const error_stats: ErrorTypeStat[] = Object.entries(errorTypes).map(([error_type, count]) => ({
    error_type,
    count: Number(count),
    percentage: totalErrors > 0 ? (Number(count) / totalErrors) * 100 : 0,
  }));

  const node_rankings: NodeDurationRank[] = (promResp.nodes || []).map((n: Record<string, unknown>) => ({
    node_name: String(n.node_name || ''),
    avg_duration: Number(n.avg_duration || 0),
    max_duration: Number(n.max_duration || 0),
    min_duration: Number(n.min_duration || 0),
    call_count: Number(n.call_count || 0),
  }));

  const recent_executions = (errorsResp.recent || []).slice(0, 10).map((e: Record<string, unknown>, i: number) => ({
    id: String(e.intent_id || `exec_${i}`),
    workflow_id: String(e.emitter || 'studio'),
    status: (e.status === 'failed' ? 'failed' : 'success') as 'success' | 'failed' | 'timeout',
    duration: Number(e.duration_ms || 500),
    timestamp: Number(e.timestamp || Date.now() / 1000) * 1000,
    node_count: 1,
  }));

  if (recent_executions.length === 0 && promResp.counters) {
    recent_executions.push({
      id: 'latest',
      workflow_id: 'engine',
      status: 'success',
      duration: 0,
      timestamp: Date.now(),
      node_count: Number(promResp.metrics?.active_agents ?? 0),
    });
  }

  return {
    summary,
    trends,
    node_rankings,
    agent_load,
    error_stats,
    recent_executions,
  };
}

export const useAnalyticsStore = create<AnalyticsState>((set, get) => ({
  data: null,
  loading: false,
  error: null,
  timeRange: 7,

  fetchAnalytics: async (timeRange) => {
    const range = timeRange ?? get().timeRange;
    set({ loading: true, timeRange: range, error: null });

    try {
      const mode = useEngineStore.getState().mode;
      const data = mode === 'real'
        ? await fetchRealAnalytics(range)
        : generateMockAnalytics(range);
      set({ data, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
      if (!get().data) {
        set({ data: generateMockAnalytics(range) });
      }
    }
  },

  setTimeRange: (range) => {
    set({ timeRange: range });
    get().fetchAnalytics(range);
  },

  reset: () => {
    set({ data: null, loading: false, error: null, timeRange: 7 });
  },
}));
