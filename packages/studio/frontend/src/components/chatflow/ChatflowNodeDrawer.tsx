import {
  Drawer, Form, Input, Button, Space, Popconfirm, Typography,
} from 'antd';
import { DeleteOutlined, SaveOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd/es/form';
import type { Node } from 'reactflow';
import type { ChatflowNodeData } from '@/types';
import { useI18n } from '@/i18n';

interface ChatflowNodeDrawerProps {
  open: boolean;
  selectedNode: Node<ChatflowNodeData> | null;
  form: FormInstance;
  onClose: () => void;
  onSave: () => void;
  onDelete: (nodeId: string) => void;
}

export function ChatflowNodeDrawer({
  open,
  selectedNode,
  form,
  onClose,
  onSave,
  onDelete,
}: ChatflowNodeDrawerProps) {
  const { t } = useI18n();

  return (
    <Drawer
      title="Node properties"
      open={open}
      onClose={onClose}
      width={400}
      extra={
        <Space>
          <Popconfirm title="Delete this node?" onConfirm={() => onDelete(selectedNode?.id ?? '')}>
            <Button danger icon={<DeleteOutlined />}>{t('common.delete')}</Button>
          </Popconfirm>
          <Button type="primary" icon={<SaveOutlined />} onClick={onSave}>{t('common.save')}</Button>
        </Space>
      }
    >
      {selectedNode && (
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="label" label="Label" rules={[{ required: true, message: 'Required' }]}>
            <Input />
          </Form.Item>
          {selectedNode.data.nodeType === 'user_input' && (
            <Form.Item name="prompt" label="Input hint">
              <Input.TextArea rows={3} placeholder="e.g. Enter your query" />
            </Form.Item>
          )}
          {selectedNode.data.nodeType === 'ai_reply' && (
            <>
              <Form.Item name="prompt" label="Reply template">
                <Input.TextArea rows={4} placeholder="Use {{variable}} syntax" />
              </Form.Item>
              <Form.Item label="Variable mapping">
                <Typography.Text type="secondary">
                  Reference upstream variables with {'{{name}}'} in the prompt
                </Typography.Text>
              </Form.Item>
            </>
          )}
          {selectedNode.data.nodeType === 'condition' && (
            <Form.Item name="condition" label="Condition" extra="JS expression with {{var}}">
              <Input.TextArea rows={3} placeholder="e.g. {{score}} > 0.8" />
            </Form.Item>
          )}
          {selectedNode.data.nodeType === 'variable' && (
            <Form.Item label="Extraction">
              <Typography.Text type="secondary">
                Configure variables extracted from the conversation
              </Typography.Text>
            </Form.Item>
          )}
        </Form>
      )}
    </Drawer>
  );
}
