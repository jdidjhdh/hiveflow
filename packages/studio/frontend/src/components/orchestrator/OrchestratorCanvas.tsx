import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
  type EdgeChange,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { ApartmentOutlined } from '@ant-design/icons';
import { useI18n } from '@/i18n';
import type { WorkflowNodeData } from '@/types';
import { orchestratorEdgeTypes } from './edges/DeletableEdge';
import { orchestratorNodeTypes } from './nodes/TaskNode';

interface OrchestratorCanvasProps {
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (params: Connection) => void;
  onInit: (instance: unknown) => void;
  onDrop: (event: React.DragEvent) => void;
  onDragOver: (event: React.DragEvent) => void;
  onNodeClick: (event: React.MouseEvent, node: Node) => void;
}

export function OrchestratorCanvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onInit,
  onDrop,
  onDragOver,
  onNodeClick,
}: OrchestratorCanvasProps) {
  const { t } = useI18n();
  const isEmpty = nodes.length === 0;

  return (
    <div className="hf-canvas-wrap">
      {isEmpty && (
        <div className="hf-canvas-empty">
          <div className="hf-canvas-empty-icon">
            <ApartmentOutlined />
          </div>
          <div className="hf-canvas-empty-title">{t('orchestrator.canvas.emptyTitle')}</div>
          <div className="hf-canvas-empty-desc">{t('orchestrator.canvas.emptyDesc')}</div>
        </div>
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onInit={onInit}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onNodeClick={onNodeClick}
        nodeTypes={orchestratorNodeTypes}
        edgeTypes={orchestratorEdgeTypes}
        fitView
        snapToGrid
        snapGrid={[20, 20]}
        deleteKeyCode={['Backspace', 'Delete']}
        defaultEdgeOptions={{
          type: 'deletable',
          style: { stroke: '#6366f1', strokeWidth: 2 },
          deletable: true,
        }}
        connectionLineStyle={{ stroke: '#6366f1', strokeWidth: 2, strokeDasharray: '5 5' }}
      >
        <Controls />
        <Background gap={20} size={1} color="#cbd5e1" />
        <MiniMap
          nodeColor={(n) => {
            const d = n.data as WorkflowNodeData;
            if (d.status === 'completed') return '#10b981';
            if (d.status === 'running') return '#3b82f6';
            if (d.status === 'failed') return '#ef4444';
            return '#cbd5e1';
          }}
          maskColor="rgba(241, 245, 249, 0.75)"
        />
      </ReactFlow>
    </div>
  );
}
