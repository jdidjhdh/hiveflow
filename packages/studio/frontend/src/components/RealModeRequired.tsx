import { Alert, Card, Typography } from 'antd';
import { useStudioMode } from '@/hooks/useStudioMode';
import { useI18n } from '@/i18n';

interface RealModeRequiredProps {
  title?: string;
  description?: string;
  children: React.ReactNode;
}

/** Renders children only in real engine mode; otherwise shows guidance. */
export default function RealModeRequired({
  title,
  description,
  children,
}: RealModeRequiredProps) {
  const { isReal } = useStudioMode();
  const { t } = useI18n();

  if (!isReal) {
    return (
      <Card>
        <Alert
          type="info"
          showIcon
          message={title ?? t('realModeRequired.title')}
          description={description ?? t('realModeRequired.description')}
        />
        <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
          {t('realModeRequired.mockHint')}
        </Typography.Paragraph>
      </Card>
    );
  }

  return <>{children}</>;
}

/** Inline banner for pages that work in mock but use simulated data. */
export function DemoDataBanner({ message }: { message?: string }) {
  const { isMock } = useStudioMode();
  const { t } = useI18n();
  if (!isMock) return null;
  return (
    <Alert
      type="warning"
      showIcon
      message={t('common.demoData')}
      description={message ?? t('common.demoDataDefault')}
      style={{ marginBottom: 16 }}
    />
  );
}
