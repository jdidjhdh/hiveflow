import { Tag, Tooltip } from 'antd';
import { useI18n, type MessageKey } from '@/i18n';
import type { PageMaturity } from '@/config/pageCapabilities';

const MATURITY_COLORS: Record<PageMaturity, string> = {
  stable: 'green',
  beta: 'blue',
  preview: 'orange',
  demo: 'gold',
};

const MATURITY_LABEL_KEYS: Record<PageMaturity, MessageKey> = {
  stable: 'maturity.stable',
  beta: 'maturity.beta',
  preview: 'maturity.preview',
  demo: 'maturity.demo',
};

const MATURITY_HINT_KEYS: Record<PageMaturity, MessageKey> = {
  stable: 'maturity.stableHint',
  beta: 'maturity.betaHint',
  preview: 'maturity.previewHint',
  demo: 'maturity.demoHint',
};

interface FeatureMaturityTagProps {
  maturity: PageMaturity;
}

export default function FeatureMaturityTag({ maturity }: FeatureMaturityTagProps) {
  const { t } = useI18n();

  return (
    <Tooltip title={t(MATURITY_HINT_KEYS[maturity])}>
      <Tag color={MATURITY_COLORS[maturity]} style={{ marginBottom: 8 }}>
        {t(MATURITY_LABEL_KEYS[maturity])}
      </Tag>
    </Tooltip>
  );
}
