import { Link } from 'react-router-dom';
import {
  Card, Space, Button, Input, Alert, Spin, Typography,
} from 'antd';
import { MessageOutlined, SendOutlined, RobotOutlined } from '@ant-design/icons';
import { useI18n } from '@/i18n';

const { Text, Paragraph } = Typography;

export interface ChatMessage {
  role: string;
  content: string;
  meta?: string;
}

interface ChatflowPreviewPanelProps {
  messages: ChatMessage[];
  chatInput: string;
  agentLoading: boolean;
  agentAvailable: boolean;
  useAgentMode: boolean;
  lastIntentId: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onPlanOnly: () => void;
  onClearMessages: () => void;
}

export function ChatflowPreviewPanel({
  messages,
  chatInput,
  agentLoading,
  agentAvailable,
  useAgentMode,
  lastIntentId,
  onInputChange,
  onSend,
  onPlanOnly,
  onClearMessages,
}: ChatflowPreviewPanelProps) {
  const { t } = useI18n();

  return (
    <div style={{ width: 380, display: 'flex', flexDirection: 'column' }}>
      <Card
        title={
          <Space>
            <MessageOutlined />
            <span>{t('chatflow.preview')}</span>
            {agentLoading && <Spin size="small" />}
          </Space>
        }
        size="small"
        extra={
          <Button size="small" onClick={onClearMessages} disabled={messages.length === 0}>
            {t('chatflow.clear')}
          </Button>
        }
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        styles={{ body: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 12 } }}
      >
        {agentAvailable && useAgentMode && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 8 }}
            message="Send uses run_query; import plans in Orchestrator or use plan-only."
          />
        )}
        {lastIntentId && (
          <div style={{ marginBottom: 8, fontSize: 12 }}>
            <Link to={`/tracer?intent_id=${encodeURIComponent(lastIntentId)}`}>Tracer</Link>
            {' · '}
            <Link to={`/replay?intent_id=${encodeURIComponent(lastIntentId)}`}>Replay</Link>
          </div>
        )}
        <div style={{ flex: 1, overflowY: 'auto', marginBottom: 12 }}>
          {messages.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
              <MessageOutlined style={{ fontSize: 32, marginBottom: 8 }} />
              <p>{t('chatflow.noMessages')}</p>
              <p style={{ fontSize: 12 }}>{t('chatflow.startHint')}</p>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom: 12,
                }}
              >
                <div
                  style={{
                    maxWidth: '80%',
                    padding: '8px 12px',
                    borderRadius: 12,
                    background: msg.role === 'user' ? '#1890ff' : '#f0f0f0',
                    color: msg.role === 'user' ? '#fff' : '#000',
                    fontSize: 13,
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  <Paragraph style={{ margin: 0, color: 'inherit' }}>{msg.content}</Paragraph>
                  {msg.meta && (
                    <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                      {msg.meta}
                    </Text>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            placeholder="Message…"
            value={chatInput}
            onChange={(e) => onInputChange(e.target.value)}
            onPressEnter={() => void onSend()}
            allowClear
            disabled={agentLoading}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={() => void onSend()} loading={agentLoading}>
            {t('chatflow.send')}
          </Button>
        </Space.Compact>
        {agentAvailable && useAgentMode && (
          <Button
            block
            style={{ marginTop: 8 }}
            icon={<RobotOutlined />}
            onClick={() => void onPlanOnly()}
            loading={agentLoading}
          >
            {t('chatflow.planOnly')}
          </Button>
        )}
      </Card>
    </div>
  );
}
