import type { MenuProps } from 'antd';

export interface OrchestratorToolbarProps {
  templateMenuItems: MenuProps['items'];
  engineMode: 'mock' | 'real';
  runtimeMode: 'core' | 'agent';
  runtimeLoading: boolean;
  executionStatus: string;
  executionProgress?: { completed: number; total: number } | null;
  onNewCanvas: () => void;
  onLoadTemplate: (key: string) => void;
  onSave: () => void;
  onImport: () => void;
  onExport: () => void;
  onExportLangGraph: () => void;
  onBatchExport: () => void;
  onAutoLayout: () => void;
  onRuntimeToggle: (checked: boolean) => void;
  onOpenAgent: () => void;
  onExecute: () => void;
  onStop: () => void;
}
