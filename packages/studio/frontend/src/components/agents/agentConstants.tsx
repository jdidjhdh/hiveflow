import {
  StopOutlined, PauseCircleOutlined, ThunderboltOutlined, CheckCircleOutlined,
} from '@ant-design/icons';
import type { Capability } from '@/types';

export const SKILL_COLORS: Record<string, string> = {
  search: '#1677ff', web: '#1677ff', retrieval: '#1677ff', crawling: '#1677ff', scraping: '#1677ff',
  nlp: '#722ed1', text_analysis: '#722ed1', summarization: '#722ed1', generate: '#722ed1',
  translation: '#a0d911', sentiment: '#722ed1', extraction: '#722ed1', chatbot: '#722ed1',
  image_processing: '#eb2f96', ocr: '#eb2f96', classification: '#eb2f96', object_detection: '#eb2f96',
  face_recognition: '#eb2f96', image_generation: '#eb2f96', video_analysis: '#eb2f96',
  data_analysis: '#13c2c2', visualization: '#13c2c2', reporting: '#13c2c2', data_processing: '#52c41a',
  preprocessing: '#52c41a', feature_engineering: '#13c2c2', forecasting: '#13c2c2', statistics: '#13c2c2',
  llm: '#2f54eb', reasoning: '#2f54eb', decision: '#2f54eb', planning: '#fa8c16', decomposition: '#fa8c16',
  analysis: '#fa8c16', thinking: '#2f54eb', problem_solving: '#fa8c16',
  security: '#fa541c', audit: '#fa541c', vulnerability_scan: '#fa541c', threat_detection: '#fa541c',
  compliance: '#fa541c', encryption: '#fa541c',
  code_generation: '#f5222d', code_review: '#f5222d', testing: '#fa541c', evaluation: '#fa541c',
  debugging: '#f5222d', documentation: '#f5222d', deployment: '#f5222d',
  ml: '#f5222d', training: '#f5222d', embedding: '#a0d911', ranking: '#a0d911',
  fine_tuning: '#f5222d', model_evaluation: '#f5222d', reinforcement_learning: '#f5222d',
  api: '#faad14', integration: '#faad14', notification: '#faad14', webhook: '#faad14',
  file_io: '#096dd9', database: '#096dd9', workflow: '#096dd9', automation: '#096dd9',
  scheduling: '#096dd9', monitoring: '#096dd9',
};

export const SUGGESTED_SKILLS = [
  'search', 'web', 'retrieval', 'crawling', 'scraping',
  'nlp', 'text_analysis', 'summarization', 'translation', 'sentiment', 'extraction', 'chatbot', 'generate',
  'image_processing', 'ocr', 'classification', 'object_detection', 'face_recognition', 'image_generation',
  'data_analysis', 'visualization', 'reporting', 'data_processing', 'preprocessing', 'feature_engineering', 'forecasting', 'statistics',
  'llm', 'reasoning', 'decision', 'planning', 'decomposition', 'analysis', 'thinking', 'problem_solving',
  'security', 'audit', 'vulnerability_scan', 'threat_detection', 'compliance', 'encryption',
  'code_generation', 'code_review', 'testing', 'evaluation', 'debugging', 'documentation', 'deployment',
  'ml', 'training', 'embedding', 'ranking', 'fine_tuning', 'model_evaluation', 'reinforcement_learning',
  'api', 'integration', 'notification', 'webhook',
  'file_io', 'database', 'workflow', 'automation', 'scheduling', 'monitoring',
];

export const STATUS_CONFIG: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  starting: { color: '#1677ff', label: '启动中', icon: <ThunderboltOutlined /> },
  running: { color: '#52c41a', label: '运行中', icon: <CheckCircleOutlined /> },
  draining: { color: '#fa8c16', label: '排水', icon: <PauseCircleOutlined /> },
  stopped: { color: '#d9d9d9', label: '已停止', icon: <StopOutlined /> },
};

export function agentColor(agent: Capability): string {
  const s = agent.skills[0] || '';
  return SKILL_COLORS[s] || '#6366f1';
}
