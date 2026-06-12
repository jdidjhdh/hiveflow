import {
  Drawer, Form, Input, Select, Slider, Button, Space, Tag, Radio, Tooltip, Collapse, Tabs, Upload,
} from 'antd';
import type { FormInstance } from 'antd/es/form';
import {
  LinkOutlined, ApiOutlined, UploadOutlined, CodeOutlined, CloudServerOutlined, SendOutlined,
} from '@ant-design/icons';
import type { Capability, CapabilitySource } from '@/types';
import { useI18n } from '@/i18n';
import { AgentAvatar } from './AgentAvatar';
import { SKILL_COLORS, SUGGESTED_SKILLS } from './agentConstants';

export interface AgentFormDrawerProps {
  open: boolean;
  editingAgent: Capability | null;
  form: FormInstance;
  capSource: CapabilitySource;
  setCapSource: (s: CapabilitySource) => void;
  onClose: () => void;
  onSubmit: () => void;
}

export function AgentFormDrawer({
  open,
  editingAgent,
  form,
  capSource,
  setCapSource,
  onClose,
  onSubmit,
}: AgentFormDrawerProps) {
  const { t } = useI18n();

  return (
    <Drawer
      title={editingAgent ? `${t('agents.edit')}: ${editingAgent.agent_id}` : t('agents.create')}
      open={open}
      onClose={onClose}
      width={480}
      extra={
        <Space>
          <Tooltip title="测试连接 (真实模式)"><Button icon={<ApiOutlined />} disabled>测试连接</Button></Tooltip>
          <Button onClick={onClose}>{t('agents.cancel')}</Button>
          <Button type="primary" onClick={onSubmit}>
            {editingAgent ? t('common.save') : t('agents.register')}
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" size="middle">
        <Form.Item name="agent_id" label="Agent ID" rules={[{ required: true, message: '请输入唯一 Agent ID' }]}>
          <Input placeholder="例如: search-agent-v1" disabled={!!editingAgent} />
        </Form.Item>
        <Form.Item name="display_name" label="显示名称">
          <Input placeholder="例如: 搜索引擎助手" />
        </Form.Item>

        {/* 自动生成头像预览 */}
        <Form.Item label="头像" tooltip="根据显示名称和技能自动生成">
          <Form.Item noStyle shouldUpdate>
            {({ getFieldValue }) => {
              const name = getFieldValue('display_name') || getFieldValue('agent_id') || 'Agent';
              const skills = (getFieldValue('skills') || []) as string[];
              const color = skills.length > 0 ? (SKILL_COLORS[skills[0]] || '#6366f1') : '#6366f1';
              return (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <AgentAvatar name={name} size={40} color={color} />
                  <span style={{ fontSize: 12, color: '#888' }}>根据名称和首项技能自动配色</span>
                </div>
              );
            }}
          </Form.Item>
        </Form.Item>

        <Form.Item name="skills" label="技能标签" rules={[{ required: true, message: '请选择至少一个技能' }]}>
          <Select mode="tags" placeholder="输入技能后回车添加" tokenSeparators={[',']} style={{ width: '100%' }}
            options={SUGGESTED_SKILLS.map(s => ({ value: s, label: s }))} />
        </Form.Item>
        <div style={{ marginTop: -16, marginBottom: 16 }}>
          <span style={{ fontSize: 11, color: '#888' }}>建议技能: </span>
          {SUGGESTED_SKILLS.slice(0, 6).map(s => (
            <Tag key={s} style={{ cursor: 'pointer' }}
              onClick={() => {
                const cur = (form.getFieldValue('skills') || []) as string[];
                if (!cur.includes(s)) form.setFieldValue('skills', [...cur, s]);
              }}>{s}</Tag>
          ))}
        </div>

        <Form.Item name="read_keys" label="可读黑板键" tooltip="允许从黑板读取的键白名单，逗号分隔">
          <Input placeholder="query, context" />
        </Form.Item>
        <Form.Item name="write_keys" label="可写黑板键" tooltip="允许写入黑板的键白名单，逗号分隔">
          <Input placeholder="search_results, error_log" />
        </Form.Item>

        <Form.Item name="weight" label={<span>权重 <span style={{ fontSize: 11, color: '#888' }}>(0.1 - 10)</span></span>} initialValue={1}>
          <Slider min={0.1} max={10} step={0.1} marks={{ 0.1: '0.1', 1: '1', 5: '5', 10: '10' }}
            tooltip={{ formatter: v => `${v} ${v! > 5 ? '(高性能)' : v! < 1 ? '(低功耗)' : '(标准)'}` }} />
        </Form.Item>

        {/* ========== 能力来源 ========== */}
        <Form.Item label="能力来源">
          <Tabs
            activeKey={capSource}
            onChange={(k) => setCapSource(k as CapabilitySource)}
            size="small"
            items={[
              {
                key: 'preset',
                label: <span><CloudServerOutlined /> 系统预置</span>,
                children: (
                  <Form.Item name="task_handler" style={{ marginBottom: 0 }}
                    tooltip="选择系统预置的后端协程函数">
                    <Select allowClear showSearch placeholder="选择预置处理器..."
                      filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}
                      options={[
                        { value: '', label: '无 (自动匹配)' },
                        { key: 'sys', label: '▸ 系统预置', options: [
                          { value: 'nlp_processor', label: 'nlp_processor' },
                          { value: 'image_processor', label: 'image_processor' },
                          { value: 'data_analyzer', label: 'data_analyzer' },
                        ]},
                      ]} />
                  </Form.Item>
                ),
              },
              {
                key: 'external_service',
                label: <span><ApiOutlined /> 外部服务调用</span>,
                children: (
                  <>
                    <Form.Item name="svc_name" label="服务名称" rules={[{ required: capSource === 'external_service', message: '请输入服务名称' }]}>
                      <Input placeholder="例如: Bing搜索" />
                    </Form.Item>
                    <Form.Item name="svc_method" label="请求方法" initialValue="GET">
                      <Select options={['GET', 'POST', 'PUT', 'DELETE'].map(v => ({ value: v, label: v }))} />
                    </Form.Item>
                    <Form.Item name="svc_url" label="URL" rules={[{ required: capSource === 'external_service', message: '请输入 API URL' }]}>
                      <Input placeholder="https://api.example.com/search" />
                    </Form.Item>
                    <Form.Item name="svc_timeout" label="超时 (秒)" initialValue={5}>
                      <Input type="number" min={1} max={30} />
                    </Form.Item>
                    <Form.Item name="svc_body" label="请求体 (JSON, 支持 {{payload.xx}} 模板)">
                      <Input.TextArea rows={4} placeholder='{"query": "{{payload.query}}"}' style={{ fontFamily: 'monospace' }} />
                    </Form.Item>
                    <Form.Item name="svc_output" label="输出映射 (JSONPath)" tooltip="提取响应中的指定字段，留空返回完整响应">
                      <Input placeholder="$.data.results" />
                    </Form.Item>
                    <Form.Item name="svc_bbkey" label="黑板写入键" tooltip="提取后写入黑板的键名">
                      <Input placeholder="results" />
                    </Form.Item>
                    <Button icon={<SendOutlined />} style={{ width: '100%' }} disabled>
                      测试调用 (需真实后端)
                    </Button>
                  </>
                ),
              },
              {
                key: 'upload',
                label: <span><UploadOutlined /> 上传代码文件</span>,
                children: (
                  <>
                    <Form.Item name="upload_handler_name" label="处理器名称">
                      <Input placeholder="自动从文件名提取" />
                    </Form.Item>
                    <Upload.Dragger
                      accept=".py"
                      maxCount={1}
                      beforeUpload={() => false}
                      style={{ marginBottom: 16 }}
                    >
                      <p><UploadOutlined style={{ fontSize: 24 }} /></p>
                      <p style={{ fontSize: 12 }}>点击或拖拽上传 .py 文件</p>
                    </Upload.Dragger>
                    <div style={{
                      background: '#1e1e1e', borderRadius: 6, padding: 12,
                      color: '#d4d4d4', fontFamily: 'monospace', fontSize: 12,
                      minHeight: 80, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <span style={{ color: '#6a9955' }}># 上传文件后此处显示代码预览</span>
                    </div>
                    <Button style={{ width: '100%', marginTop: 12 }} disabled>代码安全检查 (需真实后端)</Button>
                  </>
                ),
              },
              {
                key: 'online_edit',
                label: <span><CodeOutlined /> 在线编写</span>,
                children: (
                  <>
                    <Form.Item name="edit_handler_name" label="函数名称">
                      <Input placeholder="例如: my_custom_handler" />
                    </Form.Item>
                    <Select
                      placeholder="选择代码模板..."
                      style={{ marginBottom: 12 }}
                      options={[
                        { value: 'blank', label: '空白模板' },
                        { value: 'search_summary', label: '搜索 + 摘要' },
                        { value: 'llm_call', label: 'LLM 调用' },
                      ]}
                    />
                    <div style={{
                      background: '#1e1e1e', borderRadius: 6, overflow: 'hidden',
                      border: '1px solid #333',
                    }}>
                      <div style={{ padding: '4px 12px', background: '#2d2d2d', fontSize: 11, color: '#888' }}>
                        handler.py
                      </div>
                      <Input.TextArea
                        rows={8}
                        style={{
                          background: '#1e1e1e', color: '#d4d4d4', fontFamily: 'Consolas, Monaco, monospace',
                          fontSize: 12, border: 'none', resize: 'vertical',
                        }}
                        placeholder={`async def handler(ecm, blackboard):\n    """自定义任务处理器"""\n    query = ecm.payload.get("query")\n    # TODO: 实现逻辑\n    result = {"output": query}\n    await blackboard.put("result", result)\n    return result`}
                      />
                    </div>
                  </>
                ),
              },
            ]}
          />
        </Form.Item>

        <Form.Item name="description" label="描述">
          <Input.TextArea rows={2} placeholder="说明 Agent 的用途和能力..." />
        </Form.Item>

        {/* ========== AI 模型绑定 ========== */}
        <Collapse
          ghost
          items={[{
            key: 'model',
            label: <span><LinkOutlined /> AI 模型绑定 (高级)</span>,
            children: (
              <>
                <Form.Item name="model_enabled" valuePropName="checked" style={{ marginBottom: 8 }}>
                  <Radio.Group>
                    <Radio value={false}>不使用</Radio>
                    <Radio value={true}>绑定大模型</Radio>
                  </Radio.Group>
                </Form.Item>
                <Form.Item noStyle shouldUpdate={(prev, cur) => prev.model_enabled !== cur.model_enabled}>
                  {({ getFieldValue }) => {
                    const enabled = getFieldValue('model_enabled');
                    if (!enabled) return null;
                    return (
                      <>
                        <Form.Item name="model_provider" label="模型提供商">
                          <Select options={[
                            { value: 'openai', label: 'OpenAI' },
                            { value: 'anthropic', label: 'Anthropic' },
                            { value: 'ollama', label: 'Ollama (本地)' },
                            { value: 'custom', label: '自定义' },
                          ]} />
                        </Form.Item>
                        <Form.Item name="model_name" label="模型名称" rules={[{ required: enabled, message: '请输入模型名称' }]}>
                          <Input placeholder="gpt-4o / claude-3.5-sonnet / ..." />
                        </Form.Item>
                        <Form.Item name="system_prompt" label="系统提示词">
                          <Input.TextArea rows={3} placeholder="定义 Agent 的角色和行为..." />
                        </Form.Item>
                        <Form.Item name="temperature" label="温度 (0-2)">
                          <Slider min={0} max={2} step={0.1} marks={{ 0: '0', 0.7: '0.7', 1: '1', 2: '2' }} />
                        </Form.Item>
                        <Form.Item name="tools" label="工具列表" tooltip="Agent 可调用的外部工具，逗号分隔">
                          <Input placeholder="web_search, calculator, file_read" />
                        </Form.Item>
                      </>
                    );
                  }}
                </Form.Item>
              </>
            ),
          }]}
        />
      </Form>
    </Drawer>
  );
}
