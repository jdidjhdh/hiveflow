import type { NodeProps } from 'reactflow';
import { Handle, Position } from 'reactflow';
import { Tag } from 'antd';
import type { WorkflowNodeData, ConditionNodeData } from '@/types';
import { useI18n } from '@/i18n';

const statusColors: Record<string, string> = {
  idle: '#d9d9d9',
  running: '#1890ff',
  completed: '#52c41a',
  failed: '#ff4d4f',
};

const variantColors: Record<string, string> = {
  task: '#6366f1',
  dynamic: '#ff7a45',
  subgraph: '#52c41a',
  condition: '#722ed1',
  loop: '#fa8c16',
  code: '#f5222d',
  http: '#1890ff',
  trigger: '#13c2c2',
  hitl: '#eb2f96',
};

export function TaskNode({ id, data, selected }: NodeProps<WorkflowNodeData>) {
  const { t } = useI18n();
  const variant = data.variant || 'task';
  const variantColor = variantColors[variant] || variantColors.task;
  const isCondition = variant === 'condition';
  const conditionData = (data as unknown as { condition_data?: ConditionNodeData }).condition_data;
  const branches = conditionData?.branches || [
    { id: 'true', label: t('orchestrator.defaults.branchYes'), condition: '' },
    { id: 'false', label: t('orchestrator.defaults.branchNo'), condition: '' },
  ];

  return (
    <div
      className={`task-node status-${data.status} variant-${variant}`}
      data-testid={`canvas-node-${id}`}
      style={{ borderColor: selected ? variantColor : statusColors[data.status] }}
    >
      <Handle
        type="target"
        position={Position.Left}
        isConnectable
        style={{
          width: 16,
          height: 16,
          background: '#fff',
          border: '3px solid #52c41a',
          borderRadius: 4,
        }}
      />
      <div className="node-label" style={{ color: variantColor }}>{data.label}</div>
      {data.skills.length > 0 && (
        <div className="node-skills">
          {data.skills.map(s => (
            <span key={s} className="node-skill-tag" style={{ background: `${variantColor}18`, color: variantColor }}>
              {s}
            </span>
          ))}
        </div>
      )}
      {isCondition && (
        <div style={{ fontSize: 10, color: '#888', marginTop: 4 }}>
          {t('orchestrator.taskNode.branches', { count: branches.length })}
        </div>
      )}
      <div className="node-status-badge">
        {data.status === 'running' && <Tag color="processing">{t('orchestrator.taskNode.statusRunning')}</Tag>}
        {data.status === 'completed' && <Tag color="success">{t('orchestrator.taskNode.statusCompleted')}</Tag>}
        {data.status === 'failed' && <Tag color="error">{t('orchestrator.taskNode.statusFailed')}</Tag>}
        {data.status === 'idle' && <Tag>{t('orchestrator.taskNode.statusIdle')}</Tag>}
        {data.error && <span style={{ color: '#ff4d4f', fontSize: 10 }}> {data.error}</span>}
      </div>
      {isCondition ? (
        branches.map((branch, idx) => (
          <Handle
            key={branch.id}
            type="source"
            position={Position.Right}
            id={`branch-${branch.id}`}
            isConnectable
            style={{
              width: 14,
              height: 14,
              background: '#722ed1',
              border: '2px solid #fff',
              right: -8,
              top: `${30 + idx * 25}%`,
            }}
          />
        ))
      ) : (
        <Handle
          type="source"
          position={Position.Right}
          isConnectable
          style={{
            width: 14,
            height: 14,
            background: '#ff7a45',
            border: '2px solid #fff',
          }}
        />
      )}
    </div>
  );
}

export const orchestratorNodeTypes = { taskNode: TaskNode };
