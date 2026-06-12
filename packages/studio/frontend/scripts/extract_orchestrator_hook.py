"""One-off script to extract useOrchestratorPage hook from Orchestrator.tsx."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "src/pages/Orchestrator.tsx").read_text(encoding="utf-8")
start = src.index("export default function OrchestratorPage()")
body_start = src.index("{", start) + 1
jsx_return = src.index("\n  return (\n    <div style={{ height: '100%'", body_start)
body = src[body_start:jsx_return]
body = re.sub(
    r"\n  // 变量表单[\s\S]*?const _varColumns = \[[\s\S]*?\];\n",
    "\n",
    body,
)
body = body.replace(
    "const executeWorkflow = useCallback",
    "const runWorkflowExecution = useCallback",
)
body = body.replace(
    "const batchExportWorkflows = useCallback",
    "const runBatchExport = useCallback",
)
body = re.sub(
    r"await fetch\(`\$\{API_BASE_URL\}/api/workflows/execute`, \{[\s\S]*?\}\);",
    "await executeWorkflowApi(graph as Record<string, unknown>);",
    body,
)
body = re.sub(
    r"const response = await fetch\(`\$\{API_BASE_URL\}/api/workflows/batch-export`, \{[\s\S]*?"
    r"const data = await response\.json\(\);",
    "const data = await batchExportWorkflowsApi();",
    body,
)

header = """import { useCallback, useRef, useState, useMemo, useEffect } from 'react';
import { useNodesState, useEdgesState, addEdge, Connection, Node } from 'reactflow';
import type { MenuProps } from 'antd';
import { App } from 'antd';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { useEngineStore } from '@/store/useEngineStore';
import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';
import { useEventStore } from '@/store/useEventStore';
import type { WorkflowNodeData, ExecutionLog } from '@/types';
import { getWsManager } from '@/engine/ws/WsConnectionManager';
import { planToReactFlow, type TaskGraphPlan } from '@/utils/planToWorkflow';
import { downloadJson, downloadText } from '@/utils/downloadFile';
import { getErrorMessage } from '@/api/client';
import {
  executeWorkflow as executeWorkflowApi,
  batchExportWorkflows as batchExportWorkflowsApi,
} from '@/api/workflows';
import { builtinTemplates, templateData } from '@/components/orchestrator/constants/templates';
import { nodeTypeConfigs, type NodeTypeConfig } from '@/components/orchestrator/constants/nodeTypeConfigs';

export function useOrchestratorPage() {
"""

footer = """
  return {
    reactFlowWrapper,
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    selectedNode,
    drawerOpen,
    setDrawerOpen,
    agentDrawerOpen,
    setAgentDrawerOpen,
    agentQuery,
    setAgentQuery,
    agentLoading,
    agentResult,
    engineMode,
    runtimeMode,
    runtimeSkills,
    runtimeLoading,
    executionStatus,
    templateMenuItems,
    nodeTypeConfigs,
    onConnect,
    onDragOver,
    onDrop,
    onNodePanelDoubleClick,
    onNodeClick,
    saveNodeConfig,
    deleteSelectedNode,
    runWorkflowExecution,
    stopExecution,
    newCanvas,
    saveWorkflow,
    importWorkflow,
    exportWorkflow,
    exportCanvasAsLangGraph,
    runBatchExport,
    autoLayout,
    loadTemplate,
    handleRuntimeToggle,
    handleAgentQuery,
    handlePlanOnly,
    importPlanToCanvas,
    exportAgentPlanAsLangGraph,
    setReactFlowInstance,
  };
}
"""

out = ROOT / "src/components/orchestrator/hooks/useOrchestratorPage.ts"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(header + body + footer, encoding="utf-8")
print(f"Wrote {out} ({(header + body + footer).count(chr(10))} lines)")
