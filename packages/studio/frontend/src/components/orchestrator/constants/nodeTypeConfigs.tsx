import {
  BranchesOutlined,
  SyncOutlined,
  CodeOutlined,
  ApiOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { MessageKey, TranslateParams } from '@/i18n';
import type { WorkflowNodeData } from '@/types';

export interface NodeTypeConfig {
  type: string;
  label: string;
  variant: WorkflowNodeData['variant'];
  color: string;
  icon: JSX.Element;
}

type TFn = (key: MessageKey, params?: TranslateParams) => string;

export function getNodeTypeConfigs(t: TFn): NodeTypeConfig[] {
  return [
    { type: 'taskNode', label: t('orchestrator.nodeTypes.task'), variant: 'task', color: '#6366f1', icon: <span style={{ color: '#6366f1' }}>⬡</span> },
    { type: 'taskNode', label: t('orchestrator.nodeTypes.dynamic'), variant: 'dynamic', color: '#ff7a45', icon: <span style={{ color: '#ff7a45' }}>⬡</span> },
    { type: 'taskNode', label: t('orchestrator.nodeTypes.subgraph'), variant: 'subgraph', color: '#52c41a', icon: <span style={{ color: '#52c41a' }}>⬡</span> },
    { type: 'taskNode', label: t('orchestrator.nodeTypes.condition'), variant: 'condition', color: '#722ed1', icon: <BranchesOutlined style={{ color: '#722ed1' }} /> },
    { type: 'taskNode', label: t('orchestrator.nodeTypes.loop'), variant: 'loop', color: '#fa8c16', icon: <SyncOutlined style={{ color: '#fa8c16' }} /> },
    { type: 'taskNode', label: t('orchestrator.nodeTypes.code'), variant: 'code', color: '#f5222d', icon: <CodeOutlined style={{ color: '#f5222d' }} /> },
    { type: 'taskNode', label: t('orchestrator.nodeTypes.http'), variant: 'http', color: '#1890ff', icon: <ApiOutlined style={{ color: '#1890ff' }} /> },
    { type: 'taskNode', label: t('orchestrator.nodeTypes.trigger'), variant: 'trigger', color: '#13c2c2', icon: <ThunderboltOutlined style={{ color: '#13c2c2' }} /> },
    { type: 'taskNode', label: t('orchestrator.nodeTypes.hitl'), variant: 'hitl', color: '#eb2f96', icon: <span style={{ color: '#eb2f96' }}>👤</span> },
  ];
}

export function buildDefaultNodeData(
  t: TFn,
  variant: WorkflowNodeData['variant'],
  label: string,
): WorkflowNodeData {
  const base: WorkflowNodeData = {
    label,
    task: label,
    variant,
    skills: [],
    status: 'idle',
  };

  if (variant === 'condition') {
    return {
      ...base,
      condition_data: {
        condition: '',
        branches: [
          { id: 'true', label: t('orchestrator.defaults.branchYes'), condition: '' },
          { id: 'false', label: t('orchestrator.defaults.branchNo'), condition: '' },
        ],
        default_branch: 'false',
      },
    } as WorkflowNodeData;
  }

  if (variant === 'code') {
    return {
      ...base,
      code_data: {
        language: 'javascript',
        code: t('orchestrator.defaults.codePlaceholder'),
        input_mapping: {},
        output_mapping: {},
      },
    } as WorkflowNodeData;
  }

  if (variant === 'hitl') {
    return {
      ...base,
      hitl_config: {
        prompt: t('orchestrator.defaults.hitlPrompt'),
        action: 'approval',
        timeout_seconds: 300,
        on_timeout: 'fail',
      },
    } as WorkflowNodeData;
  }

  return base;
}
