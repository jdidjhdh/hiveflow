import { Link } from 'react-router-dom';
import {
  Drawer, Input, Button, Space, Alert, Typography, Tag,
} from 'antd';
import { FileTextOutlined, RobotOutlined } from '@ant-design/icons';
import { useI18n } from '@/i18n';

const { Text } = Typography;

export interface AgentDrawerProps {
  open: boolean;
  agentQuery: string;
  agentLoading: boolean;
  agentResult: Record<string, unknown> | null;
  runtimeSkills: string[];
  onClose: () => void;
  onQueryChange: (value: string) => void;
  onPlanOnly: () => void;
  onRunQuery: () => void;
  onImportPlan: (plan: Record<string, unknown>) => void;
  onExportLangGraph: (includePython: boolean) => void;
}

export function AgentDrawer({
  open,
  agentQuery,
  agentLoading,
  agentResult,
  runtimeSkills,
  onClose,
  onQueryChange,
  onPlanOnly,
  onRunQuery,
  onImportPlan,
  onExportLangGraph,
}: AgentDrawerProps) {
  const { t } = useI18n();

  return (
    <Drawer title={t('orchestrator.agentDrawer.title')} open={open} onClose={onClose} width={480}>
      <Alert type="info" showIcon style={{ marginBottom: 16 }} message={t('orchestrator.agentDrawer.info')} />
      {runtimeSkills.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary">{t('orchestrator.agentDrawer.registeredSkills')}</Text>
          <div style={{ marginTop: 6 }}>
            {runtimeSkills.map((s) => (
              <Tag key={s} color="purple" style={{ marginBottom: 4 }}>{s}</Tag>
            ))}
          </div>
        </div>
      )}
      <Input.TextArea
        rows={4}
        value={agentQuery}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder={t('orchestrator.agentDrawer.queryPlaceholder')}
        data-testid="agent-query-input"
        style={{ marginBottom: 12 }}
      />
      <Space direction="vertical" style={{ width: '100%' }}>
        <Button type="default" icon={<FileTextOutlined />} loading={agentLoading} block onClick={onPlanOnly} data-testid="btn-plan-only">
          {t('orchestrator.agentDrawer.planOnly')}
        </Button>
        <Button type="primary" icon={<RobotOutlined />} loading={agentLoading} block onClick={onRunQuery}>
          {t('orchestrator.agentDrawer.runQuery')}
        </Button>
      </Space>
      {agentResult && (
        <div style={{ marginTop: 16 }}>
          <Text strong>{agentResult.plan != null ? t('orchestrator.agentDrawer.executionPlan') : t('orchestrator.agentDrawer.answer')}</Text>
          <pre style={{ marginTop: 8, background: '#1e1e1e', color: '#ce9178', padding: 12, borderRadius: 8, fontSize: 13, maxHeight: 240, overflow: 'auto' }}>
            {JSON.stringify(agentResult.plan ?? agentResult.answer ?? agentResult, null, 2)}
          </pre>
          {agentResult.intent_id != null && (
            <Space style={{ marginTop: 8 }} wrap>
              <Text type="secondary" style={{ fontSize: 12 }}>intent_id: {String(agentResult.intent_id)}</Text>
              <Link to={`/tracer?intent_id=${encodeURIComponent(String(agentResult.intent_id))}`}>Tracer</Link>
              <Link to={`/replay?intent_id=${encodeURIComponent(String(agentResult.intent_id))}`}>Replay</Link>
            </Space>
          )}
          {agentResult.plan != null && typeof agentResult.plan === 'object' && (
            <Space direction="vertical" style={{ marginTop: 12, width: '100%' }}>
              <Button type="primary" ghost block data-testid="btn-import-plan" onClick={() => onImportPlan(agentResult.plan as Record<string, unknown>)}>
                {t('orchestrator.agentDrawer.importToCanvas')}
              </Button>
              <Button block data-testid="btn-export-langgraph-plan" onClick={() => onExportLangGraph(false)}>
                {t('orchestrator.agentDrawer.exportLangGraph')}
              </Button>
              <Button block type="dashed" onClick={() => onExportLangGraph(true)}>
                {t('orchestrator.agentDrawer.exportLangGraphPython')}
              </Button>
            </Space>
          )}
        </div>
      )}
    </Drawer>
  );
}
