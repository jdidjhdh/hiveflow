import { useState, useEffect } from 'react';
import { Card, Form, Select, InputNumber, Slider, Switch, Button, App, Space, Alert, Input, Tag } from 'antd';
import { SaveOutlined, RobotOutlined } from '@ant-design/icons';
import { useEngineStore } from '@/store/useEngineStore';
import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';
import { getErrorMessage } from '@/utils/api';

export default function SettingsPage() {
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
      message.success(`运行时已切换为 ${mode === 'agent' ? 'Agent 模式' : 'Core 模式'}`);
    } catch (e) {
      message.error(getErrorMessage(e));
    }
  };

  const handleAgentQuery = async () => {
    if (!agentQuery.trim()) return;
    try {
      await runQuery(agentQuery);
      message.success('Agent 查询完成');
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
    message.success('设置已保存');
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

      <Card title="Agent 运行时" style={{ marginBottom: 16 }}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="Agent 模式启用 HiveMindApp（run_query / ReAct Skill），Core 模式仅使用 DAG 编排。"
        />
        <Form layout="vertical">
          <Form.Item label="运行时模式">
            <Switch
              checked={runtimeMode === 'agent'}
              onChange={handleRuntimeChange}
              disabled={engineMode !== 'real'}
              checkedChildren="Agent"
              unCheckedChildren="Core"
            />
            {engineMode !== 'real' && (
              <span style={{ marginLeft: 8, color: '#888', fontSize: 12 }}>需切换到真实模式</span>
            )}
            {runtimeMode === 'agent' && <Tag color="purple" style={{ marginLeft: 8 }}>HiveMindApp</Tag>}
          </Form.Item>
          {runtimeMode === 'agent' && engineMode === 'real' && (
            <>
              <Form.Item label="Agent 查询 (run_query)">
                <Input.TextArea
                  rows={3}
                  value={agentQuery}
                  onChange={e => setAgentQuery(e.target.value)}
                  placeholder="输入自然语言任务..."
                />
              </Form.Item>
              <Button
                type="primary"
                icon={<RobotOutlined />}
                loading={agentLoading}
                onClick={handleAgentQuery}
              >
                执行 Agent 查询
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