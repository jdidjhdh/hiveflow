import { Handle, Position, type NodeProps } from 'reactflow';
import { Tag } from 'antd';
import {
  UserOutlined, RobotOutlined, BranchesOutlined, TagOutlined,
} from '@ant-design/icons';
import type { ChatflowNodeData } from '@/types';
import type { MessageKey } from '@/i18n';
import { useI18n } from '@/i18n';

export const NODE_COLORS: Record<string, string> = {
  user_input: '#1890ff',
  ai_reply: '#52c41a',
  condition: '#722ed1',
  variable: '#fa8c16',
};

const NODE_LABEL_KEYS: Record<string, MessageKey> = {
  user_input: 'chatflow.userInput',
  ai_reply: 'chatflow.aiReply',
  condition: 'chatflow.condition',
  variable: 'chatflow.variable',
};

export function ChatflowNode({ data, selected }: NodeProps<ChatflowNodeData>) {
  const { t } = useI18n();
  const color = NODE_COLORS[data.nodeType] || '#6366f1';
  const iconMap: Record<string, JSX.Element> = {
    user_input: <UserOutlined />,
    ai_reply: <RobotOutlined />,
    condition: <BranchesOutlined />,
    variable: <TagOutlined />,
  };

  return (
    <div
      style={{
        background: '#fff',
        border: `2px solid ${selected ? color : '#d9d9d9'}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 180,
        maxWidth: 250,
        boxShadow: selected ? `0 0 8px ${color}40` : '0 1px 3px rgba(0,0,0,0.1)',
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ width: 12, height: 12, background: '#fff', border: `2px solid ${color}`, borderRadius: '50%' }}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ color, fontSize: 14 }}>{iconMap[data.nodeType]}</span>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{data.label}</span>
        <Tag color={color} style={{ marginLeft: 'auto', fontSize: 10, padding: '0 4px' }}>
          {t(NODE_LABEL_KEYS[data.nodeType] ?? 'chatflow.userInput')}
        </Tag>
      </div>
      {data.prompt && (
        <div style={{ fontSize: 12, color: '#666', marginTop: 4, maxHeight: 60, overflow: 'hidden' }}>
          {data.prompt.length > 50 ? `${data.prompt.slice(0, 50)}...` : data.prompt}
        </div>
      )}
      {data.variable_mapping && Object.keys(data.variable_mapping).length > 0 && (
        <div style={{ marginTop: 4 }}>
          {Object.entries(data.variable_mapping).map(([k, v]) => (
            <Tag key={k} style={{ fontSize: 10, margin: 1 }}>{k} → {v}</Tag>
          ))}
        </div>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ width: 12, height: 12, background: '#fff', border: `2px solid ${color}`, borderRadius: '50%' }}
      />
    </div>
  );
}

export const chatflowNodeTypes = { chatflowNode: ChatflowNode };
