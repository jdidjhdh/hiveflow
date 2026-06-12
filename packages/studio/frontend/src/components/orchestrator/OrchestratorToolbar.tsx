import {
  Button, Tooltip, Dropdown, Divider, Switch, Tag,
} from 'antd';
import {
  PlayCircleOutlined, StopOutlined, SaveOutlined,
  FolderOpenOutlined, ExportOutlined, UndoOutlined,
  RedoOutlined, PartitionOutlined, PlusOutlined,
  AppstoreAddOutlined, BranchesOutlined, RobotOutlined,
} from '@ant-design/icons';
import { useI18n } from '@/i18n';
import type { OrchestratorToolbarProps } from './OrchestratorToolbar.types';

export type { OrchestratorToolbarProps } from './OrchestratorToolbar.types';

export function OrchestratorToolbar({
  templateMenuItems,
  engineMode,
  runtimeMode,
  runtimeLoading,
  executionStatus,
  executionProgress,
  onNewCanvas,
  onLoadTemplate,
  onSave,
  onImport,
  onExport,
  onExportLangGraph,
  onBatchExport,
  onAutoLayout,
  onRuntimeToggle,
  onOpenAgent,
  onExecute,
  onStop,
}: OrchestratorToolbarProps) {
  const { t } = useI18n();

  return (
    <div className="hf-orchestrator-toolbar">
      <div className="hf-toolbar-group">
        <Button type="primary" ghost icon={<PlusOutlined />} data-testid="btn-new" onClick={onNewCanvas}>
          {t('orchestrator.toolbar.newCanvas')}
        </Button>
        <Dropdown menu={{ items: templateMenuItems, onClick: ({ key }) => onLoadTemplate(key) }}>
          <Button icon={<AppstoreAddOutlined />} data-testid="btn-template">{t('orchestrator.toolbar.template')}</Button>
        </Dropdown>
        <Button icon={<SaveOutlined />} data-testid="btn-save" onClick={onSave}>{t('orchestrator.toolbar.save')}</Button>
        <Button icon={<FolderOpenOutlined />} data-testid="btn-import" onClick={onImport}>{t('orchestrator.toolbar.import')}</Button>
        <Button icon={<ExportOutlined />} data-testid="btn-export" onClick={onExport}>{t('orchestrator.toolbar.export')}</Button>
        <Button icon={<BranchesOutlined />} data-testid="btn-export-langgraph-canvas" onClick={onExportLangGraph}>
          LangGraph
        </Button>
        <Button icon={<ExportOutlined />} data-testid="btn-batch-export" onClick={onBatchExport}>{t('orchestrator.toolbar.batch')}</Button>
        <Divider type="vertical" style={{ height: 24, margin: '0 4px' }} />
        <Button icon={<PartitionOutlined />} data-testid="btn-layout" onClick={onAutoLayout}>{t('orchestrator.toolbar.layout')}</Button>
        <Button icon={<UndoOutlined />} disabled data-testid="btn-undo">{t('orchestrator.toolbar.undo')}</Button>
        <Button icon={<RedoOutlined />} disabled data-testid="btn-redo">{t('orchestrator.toolbar.redo')}</Button>
      </div>
      <div className="hf-toolbar-group hf-toolbar-group-actions">
        {engineMode === 'real' && (
          <>
            <Tag color={runtimeMode === 'agent' ? 'purple' : 'blue'} bordered={false}>
              {runtimeMode === 'agent' ? 'HiveMindApp' : 'Core DAG'}
            </Tag>
            <Tooltip title={runtimeMode === 'agent' ? t('orchestrator.toolbar.tooltipAgentQuery') : t('orchestrator.toolbar.tooltipCoreExecute')}>
              <Switch
                checked={runtimeMode === 'agent'}
                loading={runtimeLoading}
                checkedChildren="Agent"
                unCheckedChildren="Core"
                onChange={onRuntimeToggle}
                data-testid="runtime-mode-switch"
              />
            </Tooltip>
            {runtimeMode === 'agent' && (
              <Button icon={<RobotOutlined />} data-testid="btn-agent-query" onClick={onOpenAgent}>
                {t('orchestrator.toolbar.agentQuery')}
              </Button>
            )}
          </>
        )}
        {executionStatus === 'running' ? (
          <>
            {executionProgress && executionProgress.total > 0 && (
              <Tag color="processing" bordered={false}>
                {t('orchestrator.toolbar.nodesProgress', {
                  completed: executionProgress.completed,
                  total: executionProgress.total,
                })}
              </Tag>
            )}
            <Button danger icon={<StopOutlined />} data-testid="btn-stop" onClick={onStop}>{t('orchestrator.toolbar.stop')}</Button>
          </>
        ) : (
          <Tooltip
            title={
              runtimeMode === 'agent'
                ? t('orchestrator.toolbar.tooltipDagExecute')
                : t('orchestrator.toolbar.tooltipCoreExecute')
            }
          >
            <Button type="primary" size="middle" icon={<PlayCircleOutlined />} data-testid="btn-execute" onClick={onExecute}>
              {runtimeMode === 'agent' ? t('orchestrator.toolbar.executeDag') : t('orchestrator.toolbar.execute')}
            </Button>
          </Tooltip>
        )}
      </div>
    </div>
  );
}
