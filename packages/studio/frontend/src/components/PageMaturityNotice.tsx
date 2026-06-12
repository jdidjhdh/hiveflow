import { Alert } from 'antd';
import FeatureMaturityTag from '@/components/FeatureMaturityTag';
import { DemoDataBanner } from '@/components/RealModeRequired';
import { useStudioMode } from '@/hooks/useStudioMode';
import { useI18n } from '@/i18n';
import {
  getPageCapability,
  type PageCapabilityKey,
} from '@/config/pageCapabilities';

interface PageMaturityNoticeProps {
  pageKey: PageCapabilityKey;
}

/** Page header: maturity tag + optional demo-data banner (see CAPABILITIES.md). */
export default function PageMaturityNotice({ pageKey }: PageMaturityNoticeProps) {
  const cap = getPageCapability(pageKey);
  const { isMock } = useStudioMode();
  const { t } = useI18n();

  const bannerMessage = cap.bannerKey ? t(cap.bannerKey) : undefined;

  return (
    <div data-testid={`page-maturity-${pageKey}`}>
      <FeatureMaturityTag maturity={cap.maturity} />
      {cap.alwaysDemo && bannerMessage ? (
        <Alert
          type="warning"
          showIcon
          message={t('common.demoData')}
          description={bannerMessage}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      {!cap.alwaysDemo && cap.mockBanner && bannerMessage ? (
        <DemoDataBanner message={bannerMessage} />
      ) : null}
      {!cap.alwaysDemo && pageKey === 'auditLog' && isMock && bannerMessage ? (
        <DemoDataBanner message={bannerMessage} />
      ) : null}
    </div>
  );
}
