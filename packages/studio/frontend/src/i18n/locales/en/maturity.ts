import type { MaturityLocales } from '../types/maturity';

const maturity: MaturityLocales = {
  stable: 'Stable',
  beta: 'Beta',
  preview: 'Preview',
  demo: 'Demo',
  stableHint: 'Core feature; mock and real modes supported.',
  betaHint: 'Works in real mode; API or UX may change.',
  previewHint: 'Preview feature; may use demo data.',
  demoHint: 'Demo data only; not wired for production.',
  banner: {
    variables: 'Variables are stored locally in mock mode; real mode loads from the backend.',
    triggers: 'Triggers are stored locally in mock mode; real mode loads from the backend.',
    capabilities: 'Marketplace shows demo entries in mock mode; install requires real mode and backend.',
    dashboard: 'Dashboard metrics use MockEngine locally; real mode uses /api/metrics and WebSocket.',
    analytics: 'Charts use demo data in mock mode; real mode fetches analytics from the backend.',
    tracer: 'Intent list uses the local event bus; audit logs require real mode.',
    llmConfig: 'LLM config is browser-local in mock mode; real mode syncs with the backend.',
    knowledge: 'Knowledge base uses local mock data in mock mode; real mode uses the backend API.',
    promptTemplates: 'Prompt templates fall back to localStorage in mock mode; not production-grade persistence.',
    abTesting: 'A/B testing is a UI prototype with in-memory data only; not connected to the backend.',
    auditLog: 'Audit log requires real mode and the backend blackboard API.',
  },
};

export default maturity;
