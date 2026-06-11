/**
 * WebSocket 连接状态指示器
 * 
 * 显示实时 WebSocket 连接状态，支持：
 * - 连接/断开/重连状态显示
 * - 实时通知计数
 * - 手动重连
 */
import { useState, useEffect, useCallback } from 'react';
import { Badge, Tooltip, Popover, Button, List, Space, Tag, Typography } from 'antd';
import {
  WifiOutlined, DisconnectOutlined,
  BellOutlined, CheckCircleOutlined, WarningOutlined,
} from '@ant-design/icons';
import { getWsManager } from '@/engine/ws/WsConnectionManager';

const { Text } = Typography;

interface Notification {
  id: string;
  type: 'info' | 'warning' | 'error';
  message: string;
  timestamp: number;
  topic?: string;
}

export default function WsStatusIndicator() {
  const [connected, setConnected] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [reconnecting, setReconnecting] = useState(false);

  useEffect(() => {
    const wsManager = getWsManager();
    setConnected(wsManager.isConnected());

    // 注册事件回调
    const unregister = wsManager.onEvent((topic, data) => {
      const notif: Notification = {
        id: `${Date.now()}-${Math.random()}`,
        type: topic.includes('error') || topic.includes('failed') ? 'error' : 'info',
        message: `${topic}: ${JSON.stringify(data).slice(0, 100)}`,
        timestamp: Date.now(),
        topic,
      };
      setNotifications(prev => [notif, ...prev.slice(0, 49)]);
    });

    // 定时检查连接状态
    const interval = setInterval(() => {
      setConnected(wsManager.isConnected());
    }, 2000);

    return () => {
      unregister();
      clearInterval(interval);
    };
  }, []);

  const handleReconnect = useCallback(async () => {
    setReconnecting(true);
    const wsManager = getWsManager();
    wsManager.disconnect();
    await wsManager.connect();
    wsManager.subscribeToEngine();
    setConnected(wsManager.isConnected());
    setReconnecting(false);
  }, []);

  const handleClearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const popoverContent = (
    <div style={{ width: 400 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <Text strong>实时通知 ({notifications.length})</Text>
        {notifications.length > 0 && (
          <Button size="small" onClick={handleClearNotifications}>清空</Button>
        )}
      </div>
      <List
        size="small"
        dataSource={notifications.slice(0, 20)}
        renderItem={notif => (
          <List.Item>
            <List.Item.Meta
              avatar={
                notif.type === 'error'
                  ? <WarningOutlined style={{ color: '#ff4d4f' }} />
                  : <CheckCircleOutlined style={{ color: '#52c41a' }} />
              }
              title={
                <Space>
                  {notif.topic && <Tag color="blue">{notif.topic}</Tag>}
                  <Text style={{ fontSize: 12 }}>
                    {new Date(notif.timestamp).toLocaleTimeString()}
                  </Text>
                </Space>
              }
              description={<Text ellipsis style={{ fontSize: 12 }}>{notif.message}</Text>}
            />
          </List.Item>
        )}
        locale={{ emptyText: '暂无通知' }}
      />
    </div>
  );

  return (
    <Space>
      <Popover
        content={popoverContent}
        title="WebSocket 实时通知"
        trigger="click"
        placement="bottomRight"
      >
        <Badge count={notifications.length > 0 ? Math.min(notifications.length, 99) : undefined} size="small">
          <Button size="small" icon={<BellOutlined />}>
            通知
          </Button>
        </Badge>
      </Popover>

      <Tooltip title={connected ? 'WebSocket 已连接' : 'WebSocket 未连接'}>
        <Badge status={connected ? 'success' : 'error'}>
          <Button
            size="small"
            type="text"
            icon={connected ? <WifiOutlined /> : <DisconnectOutlined />}
            style={{ color: connected ? '#52c41a' : '#ff4d4f' }}
            onClick={handleReconnect}
            loading={reconnecting}
          />
        </Badge>
      </Tooltip>
    </Space>
  );
}
