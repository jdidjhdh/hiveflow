import React, { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button, Result, Space } from 'antd';
import { ReloadOutlined, HomeOutlined } from '@ant-design/icons';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundaryClass extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[ErrorBoundary] Caught an error:', error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Result
          status="error"
          title="页面加载失败"
          subTitle={this.state.error?.message || '发生了未知错误'}
          extra={
            <Space>
              <Button
                type="primary"
                icon={<ReloadOutlined />}
                onClick={() => this.setState({ hasError: false, error: null })}
              >
                重试
              </Button>
              <Button icon={<HomeOutlined />} onClick={() => window.location.href = '/'}>
                返回首页
              </Button>
            </Space>
          }
        />
      );
    }

    return this.props.children;
  }
}

// Hook wrapper for functional components
export function useErrorHandler() {
  const [, setError] = React.useState<Error | null>(null);

  return (error: Error | string) => {
    const e = error instanceof Error ? error : new Error(String(error));
    setError(e);
    throw e;
  };
}

export const ErrorBoundary = ErrorBoundaryClass;
export default ErrorBoundaryClass;
