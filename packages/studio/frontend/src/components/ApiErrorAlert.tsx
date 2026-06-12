import { Alert, Button } from 'antd';

interface ApiErrorAlertProps {
  error: string | null;
  onRetry?: () => void;
  title?: string;
}

/** Standard error banner for real-mode API failures. */
export default function ApiErrorAlert({ error, onRetry, title = '数据加载失败' }: ApiErrorAlertProps) {
  if (!error) return null;
  return (
    <Alert
      type="error"
      showIcon
      message={title}
      description={error}
      style={{ marginBottom: 16 }}
      action={
        onRetry ? (
          <Button size="small" onClick={onRetry}>
            重试
          </Button>
        ) : undefined
      }
    />
  );
}
