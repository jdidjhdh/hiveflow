import { create } from 'zustand';
import type { AnalyticsData, AnalyticsSummary, ExecutionTrend, NodeDurationRank, AgentLoadDist, ErrorTypeStat } from '@/types';
import { useEngineStore } from '@/store/useEngineStore';

interface AnalyticsState {
  data: AnalyticsData | null;
  loading: boolean;
  timeRange: 7 | 30;

  // Actions
  fetchAnalytics: (timeRange?: 7 | 30) => Promise<void>;
  setTimeRange: (range: 7 | 30) => void;
  reset: () => void;
}

// Generate mock analytics data
function generateMockAnalytics(timeRange: 7 | 30): AnalyticsData {
  const days = timeRange;
  const now = Date.now();
  const dayMs = 24 * 60 * 60 * 1000;

  // Generate trend data
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

  // Summary
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

  // Node duration rankings
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

  // Agent load distribution
  const engine = useEngineStore.getState().getEngine();
  const agents = engine.getAgents();
  const agent_load: AgentLoadDist[] = agents.slice(0, 6).map((agent) => ({
    agent_id: agent.agent_id,
    display_name: agent.display_name || agent.agent_id,
    execution_count: Math.floor(Math.random() * 150) + 10,
    avg_load: Math.floor(Math.random() * 80) + 5,
    success_rate: 70 + Math.random() * 28,
  }));

  // Error type stats
  const errorTypes = [
    { error_type: 'Timeout', percentage: 35 },
    { error_type: 'Connection Failed', percentage: 25 },
    { error_type: 'Invalid Response', percentage: 20 },
    { error_type: 'Resource Exhausted', percentage: 12 },
    { error_type: 'Other', percentage: 8 },
  ];
  const error_stats: ErrorTypeStat[] = errorTypes.map((e) => ({
    ...e,
    count: Math.floor(failedCount * e.percentage / 100),
  }));

  // Recent executions
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

export const useAnalyticsStore = create<AnalyticsState>((set, get) => ({
  data: null,
  loading: false,
  timeRange: 7,

  fetchAnalytics: async (timeRange) => {
    const range = timeRange ?? get().timeRange;
    set({ loading: true, timeRange: range });

    // Simulate async fetch
    await new Promise((resolve) => setTimeout(resolve, 500));

    const data = generateMockAnalytics(range);
    set({ data, loading: false });
  },

  setTimeRange: (range) => {
    set({ timeRange: range });
    get().fetchAnalytics(range);
  },

  reset: () => {
    set({ data: null, loading: false, timeRange: 7 });
  },
}));
