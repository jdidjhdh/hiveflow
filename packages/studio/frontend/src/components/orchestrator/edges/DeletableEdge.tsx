import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  useReactFlow,
  type EdgeProps,
} from 'reactflow';
import { App } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import { useI18n } from '@/i18n';

export function DeletableEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
}: EdgeProps) {
  const flowing = data?.status === 'flowing';
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const { deleteElements } = useReactFlow();
  const { message } = App.useApp();
  const { t } = useI18n();

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          strokeDasharray: flowing ? '8 4' : undefined,
          animation: flowing ? 'edge-flow 0.8s linear infinite' : undefined,
        }}
        markerEnd={markerEnd}
      />
      <EdgeLabelRenderer>
        <div
          className="edge-delete-btn"
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            pointerEvents: 'all',
          }}
          onClick={() => {
            deleteElements({ edges: [{ id }] });
            message.info(t('orchestrator.edge.deleted'));
          }}
        >
          <CloseOutlined style={{ fontSize: 11 }} />
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

export const orchestratorEdgeTypes = { deletable: DeletableEdge };
