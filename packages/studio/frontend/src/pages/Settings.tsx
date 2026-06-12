import { useState, useEffect } from 'react';
import { Card, Form, Select, InputNumber, Slider, Switch, Button, App, Space, Alert, Input, Tag } from 'antd';
import { SaveOutlined, RobotOutlined } from '@ant-design/icons';
import { useEngineStore } from '@/store/useEngineStore';
import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';
import { getErrorMessage } from '@/api';
import { useI18n } from '@/i18n';

export default function SettingsPage() {
  const { t } = useI18n();
  const engine = useEngineStore().getEngine();
  const engineMode = useEngineStore(s => s.mode);
  const config = engine.getConfig();
  const { message } = App.useApp();
  const { error } = useEngineStore();

  const [strategy, setStrategy] = useState(config.strategy);
  const [auctionTimeout, setAuctionTimeout] = useState(config.auctionTimeout);
  const [failProbability, setFailProbability] = useState(config.failProbability);
  const [delayMin, setDelayMin] = useState(config.delayRange[0]);
  const [delayMax, setDelayMax] = useState(config.delayRange[1]);
  const runtimeMode = useAgentRuntimeStore(s => s.runtimeMode);
  const agentLoading = useAgentRuntimeStore(s => s.loading);
  const fetchRuntime = useAgentRuntimeStore(s => s.fetchRuntime);
  const setRuntimeMode = useAgentRuntimeStore(s => s.setRuntimeMode);
  const runQuery = useAgentRuntimeStore(s => s.runQuery);
  const lastAnswer = useAgentRuntimeStore(s => s.lastAnswer);
  const [agentQuery, setAgentQuery] = useState('');

  useEffect(() => {
    if (engineMode === 'real') fetchRuntime();
  }, [engineMode, fetchRuntime]);

  const handleRuntimeChange = async (checked: boolean) => {
    const mode = checked ? 'agent' : 'core';
    try {
      await setRuntimeMode(mode);
      message.success(t('pages.settings.runtimeSwitched', { mode: mode === 'agent' ? t('pages.settings.agentRuntime.agent') : t('pages.settings.agentRuntime.core') }));
    } catch (e) {
      message.error(getErrorMessage(e));
    }
  };

  const handleAgentQuery = async () => {
    if (!agentQuery.trim()) return;
    try {
      await runQuery(agentQuery);
      message.success(t('pages.settings.agentRuntime.queryComplete'));
    } catch (e) {
      message.error(getErrorMessage(e));
    }
  };

  const handleSave = () => {
    engine.setConfig({
      strategy,
      auctionTimeout,
      failProbability,
      delayRange: [delayMin, delayMax],
    });
    message.success(t('pages.settings.saved'));
  };

  return (
    <div style={{ maxWidth: 700 }}>
      <h3 style={{ marginBottom: 24 }}>{t('pages.settings.title')}</h3>

      {error && (
        <Alert
          message={t('pages.settings.connectionError')}
          description={error}
          type="error"
          closable
          style={{ marginBottom: 16 }}
        />
      )}

      <Card title={t('pages.settings.agentRuntime.title')} style={{ marginBottom: 16 }}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message={t('pages.settings.agentRuntime.hint')}
        />
        <Form layout="vertical">
          <Form.Item label={t('pages.settings.agentRuntime.mode')}>
            <Switch
              checked={runtimeMode === 'agent'}
              onChange={handleRuntimeChange}
              disabled={engineMode !== 'real'}
              checkedChildren={t('pages.settings.agentRuntime.agent')}
              unCheckedChildren={t('pages.settings.agentRuntime.core')}
            />
            {engineMode !== 'real' && (
              <span style={{ marginLeft: 8, color: '#888', fontSize: 12 }}>{t('pages.settings.agentRuntime.realModeRequired')}</span>
            )}
            {runtimeMode === 'agent' && <Tag color="purple" style={{ marginLeft: 8 }}>HiveMindApp</Tag>}
          </Form.Item>
          {runtimeMode === 'agent' && engineMode === 'real' && (
            <>
              <Form.Item label={t('pages.settings.agentRuntime.query')}>
                <Input.TextArea
                  rows={3}
                  value={agentQuery}
                  onChange={e => setAgentQuery(e.target.value)}
                  placeholder={t('pages.settings.agentRuntime.queryPlaceholder')}
                />
              </Form.Item>
              <Button
                type="primary"
                icon={<RobotOutlined />}
                loading={agentLoading}
                onClick={handleAgentQuery}
              >
                {t('pages.settings.agentRuntime.runQuery')}
              </Button>
              {lastAnswer && (
                <pre style={{ marginTop: 12, background: '#f5f5f5', padding: 12, borderRadius: 6, fontSize: 13 }}>
                  {lastAnswer}
                </pre>
              )}
            </>
          )}
        </Form>
      </Card>

      <Card title={t('pages.settings.scheduling.title')} style={{ marginBottom: 16 }}>
        <Form layout="vertical">
          <Form.Item label={t('pages.settings.scheduling.strategy')}>
            <Select value={strategy} onChange={setStrategy} options={[
              { value: 'least_loaded', label: t('pages.settings.scheduling.leastLoaded') },
              { value: 'auction', label: t('pages.settings.scheduling.auction') },
            ]} />
          </Form.Item>
          {strategy === 'auction' && (
            <Form.Item label={t('pages.settings.scheduling.auctionTimeout')}>
              <InputNumber value={auctionTimeout} onChange={v => setAuctionTimeout(v ?? 5)} min={1} max={60} style={{ width: 200 }} />
            </Form.Item>
          )}
        </Form>
      </Card>

      <Card title={t('pages.settings.mock.title')} style={{ marginBottom: 16 }}>
        <Form layout="vertical">
          <Form.Item label={t('pages.settings.mock.delayRange')}>
            <Space.Compact>
              <span style={{ display: 'inline-flex', alignItems: 'center', padding: '0 8px', border: '1px solid #d9d9d9', borderRadius: '6px 0 0 6px', background: '#fafafa', fontSize: 13 }}>{t('pages.settings.mock.min')}</span>
              <InputNumber value={delayMin} onChange={v => setDelayMin(v ?? 100)} min={0} max={5000} style={{ width: 80 }} />
            </Space.Compact>
            <span>—</span>
            <Space.Compact>
              <span style={{ display: 'inline-flex', alignItems: 'center', padding: '0 8px', border: '1px solid #d9d9d9', borderRadius: '6px 0 0 6px', background: '#fafafa', fontSize: 13 }}>{t('pages.settings.mock.max')}</span>
              <InputNumber value={delayMax} onChange={v => setDelayMax(v ?? 800)} min={100} max={5000} style={{ width: 80 }} />
            </Space.Compact>
          </Form.Item>
          <Form.Item label={t('pages.settings.mock.failProbability')}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <Slider
                value={failProbability}
                onChange={setFailProbability}
                min={0}
                max={1}
                step={0.05}
                style={{ width: 300 }}
                marks={{ 0: '0%', 0.5: '50%', 1: '100%' }}
              />
              <span style={{ fontWeight: 600 }}>{(failProbability * 100).toFixed(0)}%</span>
            </div>
          </Form.Item>
        </Form>
      </Card>

      <Card title={t('pages.settings.other.title')} style={{ marginBottom: 16 }}>
        <Alert
          type="info"
          showIcon
          message={t('pages.settings.other.notPersistedTitle')}
          description={t('pages.settings.other.notPersistedDesc')}
          style={{ marginBottom: 16 }}
        />
        <Form layout="vertical">
          <Form.Item label={t('pages.settings.other.defaultTimeout')}>
            <InputNumber defaultValue={30} min={1} max={3600} style={{ width: 200 }} disabled />
          </Form.Item>
          <Form.Item label={t('pages.settings.other.maxAuditEntries')}>
            <InputNumber defaultValue={1000} min={100} max={100000} style={{ width: 200 }} disabled />
          </Form.Item>
          <Form.Item label={t('pages.settings.other.encryptedBlackboard')}>
            <Switch disabled />
            <span style={{ marginLeft: 8, color: '#888', fontSize: 12 }}>{t('pages.settings.other.encryptedHint')}</span>
          </Form.Item>
        </Form>
      </Card>

      <Button type="primary" icon={<SaveOutlined />} size="large" onClick={handleSave}>
        {t('pages.settings.save')}
      </Button>
    </div>
  );
}