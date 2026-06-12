import type { MaturityLocales } from '../types/maturity';

const maturity: MaturityLocales = {
  stable: '稳定',
  beta: 'Beta',
  preview: '预览',
  demo: '演示',
  stableHint: '核心功能，Mock 与真实模式均可用。',
  betaHint: '真实模式可用，API 或体验可能调整。',
  previewHint: '预览功能，可能含演示数据。',
  demoHint: '仅演示数据，未对接生产后端。',
  banner: {
    variables: '变量保存在浏览器本地；真实模式下会从后端加载列表。',
    triggers: '触发器保存在浏览器本地；真实模式下会从后端加载列表。',
    capabilities: '插件市场展示演示条目；安装需切换真实模式并连接后端。',
    dashboard: '仪表盘指标来自本地 MockEngine；真实模式下连接 /api/metrics 与 WebSocket。',
    analytics: '分析图表使用本地演示数据；真实模式下从后端拉取统计。',
    tracer: '意图列表来自本地事件总线；审计日志需真实模式连接后端。',
    llmConfig: 'LLM 配置在演示模式下保存在浏览器；真实模式同步后端。',
    knowledge: '知识库在演示模式下使用本地 Mock 数据；真实模式连接后端 API。',
    promptTemplates: 'Prompt 模板在演示模式或未连接后端时使用 localStorage；非生产持久化。',
    abTesting: 'A/B 测试为 UI 原型，数据保存在内存中，重启后丢失，未连接后端。',
    auditLog: '审计日志需真实模式并连接后端黑板 API。',
  },
};

export default maturity;
