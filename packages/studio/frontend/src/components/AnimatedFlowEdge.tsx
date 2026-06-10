import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from 'reactflow';
import { CloseOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { App } from 'antd';

interface AnimatedEdgeProps extends EdgeProps {
  data?: {
    animated?: boolean;
    status?: 'idle' | 'flowing' | 'completed';
  };
}

export default function AnimatedFlowEdge({
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
}: AnimatedEdgeProps) {
  const isFlowing = data?.status === 'flowing';
  const isCompleted = data?.status === 'completed';

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  // 动态计算样式
  const edgeStyle: React.CSSProperties = {
    ...style,
    stroke: isFlowing ? '#6366f1' : isCompleted ? '#52c41a' : style.stroke || '#b1b1b7',
    strokeWidth: isFlowing ? 3 : isCompleted ? 2.5 : style.strokeWidth || 1.5,
    strokeDasharray: isFlowing ? '8 4' : 'none',
    animation: isFlowing ? 'edge-flow 0.8s linear infinite' : undefined,
    transition: 'stroke 0.3s, stroke-width 0.3s, stroke-dasharray 0.3s',
  };

  return (
    <>
      <BaseEdge id={id} path={edgePath} style={edgeStyle} markerEnd={markerEnd} />
      <EdgeLabelRenderer>
        {/* 流动动画指示器 */}
        {isFlowing && (
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: 'none',
            }}
          >
            <PlayCircleOutlined
              style={{
                fontSize: 14,
                color: '#6366f1',
                animation: 'pulse 1s infinite',
              }}
            />
          </div>
        )}

        {/* 删除按钮 */}
        <div
          className="edge-delete-btn"
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX + 14}px, ${labelY - 14}px)`,
            pointerEvents: 'all',
            opacity: isFlowing ? 0.5 : 1,
          }}
        >
          <CloseOutlined style={{ fontSize: 11 }} />
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
