import ReactFlow, {
  Background, Controls, MiniMap, Panel,
  type Connection, type Edge, type Node, type NodeChange, type EdgeChange,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Tag } from 'antd';
import type { ChatflowNodeData } from '@/types';
import { useI18n } from '@/i18n';
import { chatflowNodeTypes } from './ChatflowNode';

interface ChatflowCanvasProps {
  nodes: Node<ChatflowNodeData>[];
  edges: Edge[];
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (params: Connection) => void;
  onNodeClick: (event: React.MouseEvent, node: Node) => void;
}

export function ChatflowCanvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onNodeClick,
}: ChatflowCanvasProps) {
  const { t } = useI18n();

  return (
    <div style={{ flex: 1, border: '1px solid #d9d9d9', borderRadius: 8 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        nodeTypes={chatflowNodeTypes}
        fitView
        snapToGrid
        snapGrid={[20, 20]}
      >
        <Controls />
        <MiniMap />
        <Background gap={16} size={1} />
        <Panel position="top-right">
          <Tag color="blue">{t('chatflow.clickToEdit')}</Tag>
        </Panel>
      </ReactFlow>
    </div>
  );
}
