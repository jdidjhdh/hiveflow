import type { MenuProps } from 'antd';
import {
  ApartmentOutlined,
  RobotOutlined,
  DashboardOutlined,
  EyeOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
  SettingOutlined,
  ShopOutlined,
  ShareAltOutlined,
  BellOutlined,
  CloudServerOutlined,
  BookOutlined,
  MessageOutlined,
  BarChartOutlined,
  BulbOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  CheckOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import type { MessageKey } from '@/i18n';

type TFn = (key: MessageKey) => string;

export function buildMenuItems(t: TFn): MenuProps['items'] {
  const primaryMenuItems: MenuProps['items'] = [
    { key: '/orchestrator', icon: <ApartmentOutlined />, label: t('nav.orchestrator') },
    { key: '/agents', icon: <RobotOutlined />, label: t('nav.agents') },
    { key: '/chatflow', icon: <MessageOutlined />, label: t('nav.chatflow') },
    { key: '/analytics', icon: <BarChartOutlined />, label: t('nav.analytics') },
    { key: '/approvals', icon: <CheckOutlined />, label: t('nav.approvals') },
    { key: '/dashboard', icon: <DashboardOutlined />, label: t('nav.dashboard') },
  ];

  const advancedMenuItems: MenuProps['items'] = [
    { key: '/capabilities', icon: <ShopOutlined />, label: t('nav.capabilities') },
    { key: '/knowledge', icon: <BookOutlined />, label: t('nav.knowledge') },
    { key: '/prompt-templates', icon: <BulbOutlined />, label: t('nav.promptTemplates') },
    { key: '/ab-testing', icon: <ExperimentOutlined />, label: t('nav.abTesting') },
    { key: '/audit-log', icon: <FileSearchOutlined />, label: t('nav.auditLog') },
    { key: '/tracer', icon: <EyeOutlined />, label: t('nav.tracer') },
    { key: '/replay', icon: <HistoryOutlined />, label: t('nav.replay') },
    { key: '/blackboard', icon: <DatabaseOutlined />, label: t('nav.blackboard') },
    { key: '/events', icon: <ThunderboltOutlined />, label: t('nav.events') },
    { key: '/variables', icon: <ShareAltOutlined />, label: t('nav.variables') },
    { key: '/triggers', icon: <BellOutlined />, label: t('nav.triggers') },
    { key: '/llm-config', icon: <CloudServerOutlined />, label: t('nav.llmConfig') },
    { key: '/settings', icon: <SettingOutlined />, label: t('nav.settings') },
  ];

  return [
    ...primaryMenuItems,
    { type: 'divider' },
    {
      key: 'advanced',
      label: t('nav.advanced'),
      type: 'group',
      children: advancedMenuItems,
    },
  ];
}

export const routePaths = [
  '/orchestrator',
  '/agents',
  '/chatflow',
  '/analytics',
  '/approvals',
  '/dashboard',
  '/capabilities',
  '/knowledge',
  '/prompt-templates',
  '/ab-testing',
  '/audit-log',
  '/tracer',
  '/replay',
  '/blackboard',
  '/events',
  '/variables',
  '/triggers',
  '/llm-config',
  '/settings',
] as const;
