import { useI18n } from '@/i18n';
import type { NodeTypeConfig } from './constants/nodeTypeConfigs';

interface NodeLibraryPanelProps {
  configs: NodeTypeConfig[];
  onAddNode: (cfg: NodeTypeConfig) => void;
}

export function NodeLibraryPanel({ configs, onAddNode }: NodeLibraryPanelProps) {
  const { t } = useI18n();

  return (
    <div className="hf-node-library">
      <div className="hf-node-library-title">{t('orchestrator.nodeLibrary.title')}</div>
      {configs.map((cfg) => (
        <div
          key={`${cfg.variant}-${cfg.label}`}
          className="dnd-node-item"
          data-testid={`node-${cfg.variant || 'task'}`}
        >
          <div
            className="dnd-node-item-body"
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData('application/reactflow-type', cfg.type);
              e.dataTransfer.setData('application/reactflow-label', cfg.label);
              e.dataTransfer.setData('application/reactflow-variant', cfg.variant || 'task');
              e.dataTransfer.effectAllowed = 'move';
            }}
            onDoubleClick={() => onAddNode(cfg)}
            title={t('orchestrator.nodeLibrary.doubleClickHint')}
          >
            <span>{cfg.icon} {cfg.label}</span>
          </div>
          <button
            type="button"
            className="hf-node-add-btn"
            data-testid={`btn-add-${cfg.variant || 'task'}`}
            aria-label={`Add ${cfg.label}`}
            onClick={() => onAddNode(cfg)}
          >
            +
          </button>
        </div>
      ))}
    </div>
  );
}
