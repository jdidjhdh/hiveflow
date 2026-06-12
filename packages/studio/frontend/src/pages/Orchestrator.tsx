import { Alert } from 'antd';
import { useI18n } from '@/i18n';
import { GoldenPathBanner } from '@/components/orchestrator/GoldenPathBanner';
import { NodeLibraryPanel } from '@/components/orchestrator/NodeLibraryPanel';
import { OrchestratorToolbar } from '@/components/orchestrator/OrchestratorToolbar';
import { OrchestratorCanvas } from '@/components/orchestrator/OrchestratorCanvas';
import { NodeConfigDrawer } from '@/components/orchestrator/OrchestratorDrawers';
import { AgentDrawer } from '@/components/orchestrator/AgentDrawer';
import { useOrchestratorPage } from '@/components/orchestrator/hooks/useOrchestratorPage';

export default function OrchestratorPage() {
  const { t } = useI18n();
  const p = useOrchestratorPage();
  const canvasEmpty = p.nodes.length === 0;

  return (
    <div
      className="hf-orchestrator-page"
      style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
      ref={p.reactFlowWrapper}
      data-testid={p.canvasHydrated ? 'orchestrator-ready' : undefined}
    >
      <OrchestratorToolbar
        templateMenuItems={p.templateMenuItems}
        engineMode={p.engineMode}
        runtimeMode={p.runtimeMode}
        runtimeLoading={p.runtimeLoading}
        executionStatus={p.executionStatus}
        executionProgress={p.executionProgress}
        onNewCanvas={p.newCanvas}
        onLoadTemplate={p.loadTemplate}
        onSave={p.saveWorkflow}
        onImport={p.importWorkflow}
        onExport={p.exportWorkflow}
        onExportLangGraph={p.exportCanvasAsLangGraph}
        onBatchExport={p.runBatchExport}
        onAutoLayout={p.autoLayout}
        onRuntimeToggle={p.handleRuntimeToggle}
        onOpenAgent={() => p.setAgentDrawerOpen(true)}
        onExecute={p.runWorkflowExecution}
        onStop={p.stopExecution}
      />

      <GoldenPathBanner
        engineMode={p.engineMode}
        runtimeMode={p.runtimeMode}
        canvasEmpty={canvasEmpty}
        onOpenAgent={() => p.setAgentDrawerOpen(true)}
      />

      {p.engineMode === 'real' && p.runtimeMode === 'agent' && (
        <Alert
          type="info"
          showIcon
          closable
          style={{ marginBottom: 12 }}
          message={t('orchestrator.agentModeBanner')}
        />
      )}

      <div className="hf-orchestrator-body">
        <NodeLibraryPanel configs={p.nodeTypeConfigs} onAddNode={p.onAddNodeFromLibrary} />
        <OrchestratorCanvas
          nodes={p.nodes}
          edges={p.edges}
          onNodesChange={p.onNodesChange}
          onEdgesChange={p.onEdgesChange}
          onConnect={p.onConnect}
          onInit={(instance) => p.setReactFlowInstance(instance as NonNullable<Parameters<typeof p.setReactFlowInstance>[0]>)}
          onDrop={p.onDrop}
          onDragOver={p.onDragOver}
          onNodeClick={p.onNodeClick}
        />
      </div>

      <NodeConfigDrawer
        open={p.drawerOpen}
        selectedNode={p.selectedNode}
        onClose={() => p.setDrawerOpen(false)}
        onSave={p.saveNodeConfig}
        onDelete={p.deleteSelectedNode}
      />

      <AgentDrawer
        open={p.agentDrawerOpen}
        agentQuery={p.agentQuery}
        agentLoading={p.agentLoading}
        agentResult={p.agentResult}
        runtimeSkills={p.runtimeSkills}
        onClose={() => p.setAgentDrawerOpen(false)}
        onQueryChange={p.setAgentQuery}
        onPlanOnly={p.handlePlanOnly}
        onRunQuery={p.handleAgentQuery}
        onImportPlan={p.importPlanToCanvas}
        onExportLangGraph={p.exportAgentPlanAsLangGraph}
      />
    </div>
  );
}
