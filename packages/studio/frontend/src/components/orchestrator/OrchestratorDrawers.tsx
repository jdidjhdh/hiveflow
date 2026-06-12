import {
  Drawer, Form, Input, InputNumber, Select, Button, Alert, Typography,
} from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import type { Node } from 'reactflow';
import type { WorkflowNodeData, ConditionNodeData, CodeNodeData } from '@/types';
import { useI18n } from '@/i18n';

const { Text } = Typography;
const { TextArea } = Input;

interface NodeConfigDrawerProps {
  open: boolean;
  selectedNode: Node<WorkflowNodeData> | null;
  onClose: () => void;
  onSave: (values: Record<string, unknown>) => void;
  onDelete: () => void;
}

export function NodeConfigDrawer({
  open,
  selectedNode,
  onClose,
  onSave,
  onDelete,
}: NodeConfigDrawerProps) {
  const { t } = useI18n();

  return (
    <Drawer
      title={t('orchestrator.nodeDrawer.title')}
      open={open}
      onClose={onClose}
      width={500}
      data-testid="node-config-drawer"
      extra={
        <Button danger icon={<DeleteOutlined />} onClick={onDelete}>
          {t('orchestrator.nodeDrawer.deleteNode')}
        </Button>
      }
    >
      {selectedNode && (
        <Form
          layout="vertical"
          initialValues={{
            label: selectedNode.data.label,
            task: selectedNode.data.task,
            skills: selectedNode.data.skills,
            max_attempts: selectedNode.data.retry_policy?.max_attempts,
            backoff_type: selectedNode.data.retry_policy?.backoff_type || 'constant',
            backoff_base: selectedNode.data.retry_policy?.backoff_base || 1,
            max_backoff: selectedNode.data.retry_policy?.max_backoff || 30,
            on_failure: selectedNode.data.on_failure,
            state_key: selectedNode.data.expectation?.state_key,
            validation: selectedNode.data.expectation?.validation,
            deadline: selectedNode.data.expectation?.deadline || 30,
            condition: (selectedNode.data as unknown as { condition_data?: ConditionNodeData }).condition_data?.condition || '',
            branches: (selectedNode.data as unknown as { condition_data?: ConditionNodeData }).condition_data?.branches || [],
            default_branch: (selectedNode.data as unknown as { condition_data?: ConditionNodeData }).condition_data?.default_branch || 'false',
            language: (selectedNode.data as unknown as { code_data?: CodeNodeData }).code_data?.language || 'javascript',
            code: (selectedNode.data as unknown as { code_data?: CodeNodeData }).code_data?.code || '',
            hitl_prompt: selectedNode.data.hitl_config?.prompt || '',
            hitl_action: selectedNode.data.hitl_config?.action || 'approval',
            hitl_timeout: selectedNode.data.hitl_config?.timeout_seconds || 300,
            hitl_on_timeout: selectedNode.data.hitl_config?.on_timeout || 'fail',
          }}
          onFinish={onSave}
        >
          <Form.Item name="label" label={t('orchestrator.nodeDrawer.nodeName')} rules={[{ required: true }]}>
            <Input data-testid="input-node-label" />
          </Form.Item>
          <Form.Item name="task" label={t('orchestrator.nodeDrawer.taskFn')} rules={[{ required: true }]}>
            <Input data-testid="input-node-task" placeholder={t('orchestrator.nodeDrawer.taskFnPlaceholder')} />
          </Form.Item>
          <Form.Item name="skills" label={t('orchestrator.nodeDrawer.skills')}>
            <Select mode="tags" placeholder={t('orchestrator.nodeDrawer.skillsPlaceholder')} />
          </Form.Item>

          {selectedNode.data.variant === 'condition' && (
            <>
              <Form.Item name="condition" label={t('orchestrator.nodeDrawer.conditionExpr')}>
                <Input.TextArea data-testid="input-node-condition" rows={2} placeholder={t('orchestrator.nodeDrawer.conditionPlaceholder')} />
              </Form.Item>
              <Alert
                data-testid="node-var-syntax-alert"
                message={t('orchestrator.nodeDrawer.varSyntaxAlert')}
                description={<Text code>{`{{variable_name}}`}</Text>}
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
              />
            </>
          )}

          {selectedNode.data.variant === 'code' && (
            <>
              <Form.Item name="language" label={t('orchestrator.nodeDrawer.language')}>
                <Select data-testid="select-node-language">
                  <Select.Option value="javascript">JavaScript</Select.Option>
                  <Select.Option value="python">Python</Select.Option>
                </Select>
              </Form.Item>
              <Form.Item name="code" label={t('orchestrator.nodeDrawer.code')}>
                <TextArea data-testid="input-node-code" rows={12} style={{ fontFamily: 'monospace', fontSize: 13, backgroundColor: '#1e1e1e', color: '#d4d4d4' }} />
              </Form.Item>
            </>
          )}

          {selectedNode.data.variant === 'hitl' && (
            <>
              <Form.Item name="hitl_prompt" label={t('orchestrator.nodeDrawer.hitlPrompt')} rules={[{ required: true }]}>
                <Input.TextArea rows={2} />
              </Form.Item>
              <Form.Item name="hitl_action" label={t('orchestrator.nodeDrawer.hitlAction')}>
                <Select>
                  <Select.Option value="approval">{t('orchestrator.nodeDrawer.hitlActionApproval')}</Select.Option>
                  <Select.Option value="review">{t('orchestrator.nodeDrawer.hitlActionReview')}</Select.Option>
                  <Select.Option value="input">{t('orchestrator.nodeDrawer.hitlActionInput')}</Select.Option>
                </Select>
              </Form.Item>
              <Form.Item name="hitl_timeout" label={t('orchestrator.nodeDrawer.hitlTimeout')}>
                <InputNumber min={30} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="hitl_on_timeout" label={t('orchestrator.nodeDrawer.hitlOnTimeout')}>
                <Select>
                  <Select.Option value="fail">{t('orchestrator.nodeDrawer.timeoutFail')}</Select.Option>
                  <Select.Option value="approve">{t('orchestrator.nodeDrawer.timeoutApprove')}</Select.Option>
                  <Select.Option value="skip">{t('orchestrator.nodeDrawer.timeoutSkip')}</Select.Option>
                </Select>
              </Form.Item>
            </>
          )}

          <Form.Item name="state_key" label={t('orchestrator.nodeDrawer.stateKey')}>
            <Input placeholder={t('orchestrator.nodeDrawer.stateKeyPlaceholder')} />
          </Form.Item>
          <Form.Item name="deadline" label={t('orchestrator.nodeDrawer.deadline')}>
            <InputNumber min={1} max={3600} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="max_attempts" label={t('orchestrator.nodeDrawer.maxRetries')}>
            <InputNumber min={1} max={10} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="on_failure" label={t('orchestrator.nodeDrawer.onFailure')}>
            <Select allowClear placeholder={t('orchestrator.nodeDrawer.onFailurePlaceholder')} options={[
              { value: 'abort', label: t('orchestrator.nodeDrawer.onFailureAbort') },
              { value: 'skip', label: t('orchestrator.nodeDrawer.onFailureSkip') },
            ]} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block data-testid="btn-save-node-config">{t('orchestrator.nodeDrawer.saveConfig')}</Button>
          </Form.Item>
        </Form>
      )}
    </Drawer>
  );
}
