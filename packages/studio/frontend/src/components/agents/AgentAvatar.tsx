interface AgentAvatarProps {
  name: string;
  size?: number;
  color?: string;
}

export function AgentAvatar({ name, size = 36, color = '#6366f1' }: AgentAvatarProps) {
  const initial = (name || '?')[0].toUpperCase();
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" style={{ flexShrink: 0 }}>
      <circle cx={18} cy={18} r={18} fill={color} opacity={0.12} />
      <circle cx={18} cy={18} r={16} fill="none" stroke={color} strokeWidth={1.5} opacity={0.35} />
      <text
        x={18}
        y={18}
        textAnchor="middle"
        dominantBaseline="central"
        fill={color}
        fontSize={16}
        fontWeight={600}
        fontFamily="system-ui, sans-serif"
      >
        {initial}
      </text>
    </svg>
  );
}
