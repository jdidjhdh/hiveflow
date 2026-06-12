import { Button, Space, Card, Tag, Divider, Switch, Popconfirm } from 'antd';
import {
  PlayCircleOutlined, SaveOutlined, FolderOpenOutlined,
  UserOutlined, RobotOutlined, BranchesOutlined,
  TagOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { useI18n } from '@/i18n';
import type { ChatflowNodeData } from '@/types';

interface ChatflowToolbarProps {
  engineMode: 'mock' | 'real';
  agentAvailable: boolean;
  useAgentMode: boolean;
  nodeCount: number;
  onUseAgentModeChange: (checked: boolean) => void;
  onAddNode: (type: ChatflowNodeData['nodeType']) => void;
  onSave: () => void;
  onLoad: () => void;
  onExecute: () => void;
  onClear: () => void;
}

export function ChatflowToolbar({
  engineMode,
  agentAvailable,
  useAgentMode,
  nodeCount,
  onUseAgentModeChange,
  onAddNode,
  onSave,
  onLoad,
  onExecute,
  onClear,
}: ChatflowToolbarProps) {
  const { t } = useI18n();

  return (
    <Card size="small" style={{ marginBottom: 12 }}>
      <Space wrap>
        {engineMode === 'real' && (
          <>
            <Tag color={agentAvailable ? 'purple' : 'default'}>
              {agentAvailable ? 'Agent ready' : 'Core / Agent inactive'}
            </Tag>
            <Switch
              checked={useAgentMode}
              onChange={onUseAgentModeChange}
              disabled={!agentAvailable}
              checkedChildren="Agent"
              unCheckedChildren="Mock"
            />
          </>
        )}
        <Button type="primary" icon={<UserOutlined />} onClick={() => onAddNode('user_input')}>
          {t('chatflow.userInput')}
        </Button>
        <Button icon={<RobotOutlined />} onClick={() => onAddNode('ai_reply')}>
          {t('chatflow.aiReply')}
        </Button>
        <Button icon={<BranchesOutlined />} onClick={() => onAddNode('condition')}>
          {t('chatflow.condition')}
        </Button>
        <Button icon={<TagOutlined />} onClick={() => onAddNode('variable')}>
          {t('chatflow.variable')}
        </Button>
        <Divider type="vertical" />
        <Button icon={<SaveOutlined />} onClick={onSave}>{t('chatflow.save')}</Button>
        <Button icon={<FolderOpenOutlined />} onClick={onLoad}>{t('chatflow.load')}</Button>
        <Divider type="vertical" />
        <Button type="primary" icon={<PlayCircleOutlined />} onClick={onExecute} disabled={nodeCount === 0}>
          {t('chatflow.execute')}
        </Button>
        <Popconfirm title="Clear canvas?" onConfirm={onClear}>
          <Button icon={<DeleteOutlined />} danger>{t('chatflow.clear')}</Button>
        </Popconfirm>
        <Tag style={{ marginLeft: 8 }}>{nodeCount} nodes</Tag>
      </Space>
    </Card>
  );
}
