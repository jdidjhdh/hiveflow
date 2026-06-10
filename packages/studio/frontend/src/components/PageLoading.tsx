import { Spin } from 'antd';
import type { ReactNode } from 'react';

interface PageLoadingProps {
  size?: 'small' | 'default' | 'large';
  text?: string;
  fullScreen?: boolean;
  children?: ReactNode;
}

export default function PageLoading({
  size = 'large',
  text = '加载中...',
  fullScreen = false,
  children,
}: PageLoadingProps) {
  if (children) {
    return <Spin size={size} tip={text}>{children}</Spin>;
  }

  if (fullScreen) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        flexDirection: 'column',
        gap: 16,
      }}>
        <Spin size={size} />
        {text && <span style={{ color: '#888' }}>{text}</span>}
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      padding: '48px 0',
      flexDirection: 'column',
      gap: 16,
    }}>
      <Spin size={size} />
      {text && <span style={{ color: '#888' }}>{text}</span>}
    </div>
  );
}
