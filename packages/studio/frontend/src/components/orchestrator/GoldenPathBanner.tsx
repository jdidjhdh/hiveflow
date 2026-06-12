import { useState } from 'react';
import { Button, Space, Typography } from 'antd';
import { CloseOutlined, RocketOutlined } from '@ant-design/icons';
import { useI18n } from '@/i18n';
import zh from '@/i18n/locales/zh';
import en from '@/i18n/locales/en';

const STORAGE_KEY = 'hiveflow_golden_path_dismissed';

interface GoldenPathBannerProps {
  engineMode: 'mock' | 'real';
  runtimeMode: 'core' | 'agent';
  canvasEmpty: boolean;
  onOpenAgent: () => void;
}

export function GoldenPathBanner({
  engineMode,
  runtimeMode,
  canvasEmpty,
  onOpenAgent,
}: GoldenPathBannerProps) {
  const { t, locale } = useI18n();
  const steps = locale === 'zh' ? zh.goldenPath.steps : en.goldenPath.steps;
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(STORAGE_KEY) === '1',
  );

  if (dismissed || !canvasEmpty) {
    return null;
  }

  return (
    <div className="hf-golden-path" data-testid="golden-path-banner">
      <div className="hf-golden-path-head">
        <div>
          <div className="hf-golden-path-title">
            <RocketOutlined style={{ marginRight: 8 }} />
            {t('goldenPath.title')}
          </div>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            {t('goldenPath.subtitle')}
          </Typography.Text>
        </div>
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined />}
          aria-label="Dismiss"
          onClick={() => {
            localStorage.setItem(STORAGE_KEY, '1');
            setDismissed(true);
          }}
        />
      </div>
      <div className="hf-golden-path-steps">
        {steps.map((step, i) => (
          <span key={step} className="hf-golden-path-step">{i + 1}. {step}</span>
        ))}
      </div>
      <Space wrap>
        {engineMode === 'mock' && (
          <Typography.Text type="warning">{t('goldenPath.switchReal')}</Typography.Text>
        )}
        {engineMode === 'real' && runtimeMode !== 'agent' && (
          <Typography.Text type="warning">{t('goldenPath.switchAgent')}</Typography.Text>
        )}
        {engineMode === 'real' && runtimeMode === 'agent' && (
          <Button type="primary" size="small" data-testid="golden-path-open-agent" onClick={onOpenAgent}>
            {t('goldenPath.openAgent')}
          </Button>
        )}
      </Space>
    </div>
  );
}
