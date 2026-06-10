import { useState, useEffect } from 'react';
import { Card, Form, Select, InputNumber, Slider, Switch, Button, Divider, App, Space, Alert } from 'antd';
import { SaveOutlined, ExperimentOutlined } from '@ant-design/icons';
import { useEngineStore } from '@/store/useEngineStore';
import { getWsManager } from '@/engine/ws/WsConnectionManager';
import { API_BASE_URL } from '@/utils/api';

export default function SettingsPage() {
  const engine = useEngineStore().getEngine();
  const config = engine.getConfig();
  const { message } = App.useApp();
  const { connected, error } = useEngineStore();

  const [strategy, setStrategy] = useState(config.strategy);
  const [auctionTimeout, setAuctionTimeout] = useState(config.auctionTimeout);
  const [failProbability, setFailProbability] = useState(config.failProbability);
  const [delayMin, setDelayMin] = useState(config.delayRange[0]);
  const [delayMax, setDelayMax] = useState(config.delayRange[1]);
  const wsBaseUrl = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
  const [wsUrl, setWsUrl] = useState(`${wsBaseUrl}/ws`);
  const [connecting, setConnecting] = useState(false);

  const handleSave = () => {
    engine.setConfig({
      strategy,
      auctionTimeout,
      failProbability,
      delayRange: [delayMin, delayMax],
    });
    message.success('设置已保存');
  };

  const handleConnect = async () => {
    setConnecting(true);
    try {
      await useEngineStore.getState().connect(wsUrl);
      message.success('WebSocket 已连接');
    } catch (e) {
      message.error('连接失败: ' + String(e));
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = () => {
    useEngineStore.getState().disconnect();
    message.info('已断开连接');
  };

  return (
    <div style={{ maxWidth: 700 }}>
      <h3 style={{ marginBottom: 24 }}>系统设置</h3>

      {/* WebSocket 连接状态 */}
      {error && (
        <Alert
          message="连接错误"
          description={error}
          type="error"
          closable
          style={{ marginBottom: 16 }}
        />
      )}

      <Card title="调度策略" style={{ marginBottom: 16 }}>
        <Form layout="vertical">
          <Form.Item label="调度策略">
            <Select value={strategy} onChange={setStrategy} options={[
              { value: 'least_loaded', label: 'Least Loaded — 优先分配给负载最低的 Worker' },
              { value: 'auction', label: 'Auction — 拍卖模式，收集出价后选择最优 Worker' },
            ]} />
          </Form.Item>
          {strategy === 'auction' && (
            <Form.Item label="拍卖超时 (秒)">
              <InputNumber value={auctionTimeout} onChange={v => setAuctionTimeout(v ?? 5)} min={1} max={60} style={{ width: 200 }} />
            </Form.Item>
          )}
        </Form>
      </Card>

      <Card title="模拟模式设置" style={{ marginBottom: 16 }}>
        <Form layout="vertical">
          <Form.Item label="模拟延迟范围 (毫秒)">
            <Space.Compact>
              <span style={{ display: 'inline-flex', alignItems: 'center', padding: '0 8px', border: '1px solid #d9d9d9', borderRadius: '6px 0 0 6px', background: '#fafafa', fontSize: 13 }}>最小</span>
              <InputNumber value={delayMin} onChange={v => setDelayMin(v ?? 100)} min={0} max={5000} style={{ width: 80 }} />
            </Space.Compact>
            <span>—</span>
            <Space.Compact>
              <span style={{ display: 'inline-flex', alignItems: 'center', padding: '0 8px', border: '1px solid #d9d9d9', borderRadius: '6px 0 0 6px', background: '#fafafa', fontSize: 13 }}>最大</span>
              <InputNumber value={delayMax} onChange={v => setDelayMax(v ?? 800)} min={100} max={5000} style={{ width: 80 }} />
            </Space.Compact>
          </Form.Item>
          <Form.Item label="故障注入概率">
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

      <Card title="其他设置" style={{ marginBottom: 16 }}>
        <Form layout="vertical">
          <Form.Item label="默认意图超时 (秒)">
            <InputNumber defaultValue={30} min={1} max={3600} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item label="黑板最大审计条目">
            <InputNumber defaultValue={1000} min={100} max={100000} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item label="加密黑板 (仅真实模式)">
            <Switch disabled />
            <span style={{ marginLeft: 8, color: '#888', fontSize: 12 }}>需通过后端环境变量配置加密密钥</span>
          </Form.Item>
        </Form>
      </Card>

      <Button type="primary" icon={<SaveOutlined />} size="large" onClick={handleSave}>
        保存设置
      </Button>
    </div>
  );
}