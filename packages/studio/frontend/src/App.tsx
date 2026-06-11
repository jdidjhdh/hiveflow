import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Tag, Switch } from 'antd';
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
import type { MenuProps } from 'antd';
import { useEngineStore } from '@/store/useEngineStore';
import ErrorBoundary from '@/components/ErrorBoundary';
import WsStatusIndicator from '@/components/WsStatusIndicator';
import RuntimeStatusBar from '@/components/RuntimeStatusBar';
import OrchestratorPage from '@/pages/Orchestrator';
import AgentsPage from '@/pages/Agents';
import DashboardPage from '@/pages/Dashboard';
import TracerPage from '@/pages/Tracer';
import BlackboardPage from '@/pages/Blackboard';
import EventsPage from '@/pages/Events';
import SettingsPage from '@/pages/Settings';
import CapabilityMarketPage from '@/pages/CapabilityMarket';
import VariablesPage from '@/pages/Variables';
import TriggersPage from '@/pages/Triggers';
import LLMConfigPage from '@/pages/LLMConfig';
import KnowledgeBasePage from '@/pages/KnowledgeBase';
import ChatflowPage from '@/pages/Chatflow';
import AnalyticsPage from '@/pages/Analytics';
import PromptTemplatesPage from '@/pages/PromptTemplates';
import ABTestingPage from '@/pages/ABTesting';
import AuditLogPage from '@/pages/AuditLog';
import ApprovalsPage from '@/pages/Approvals';
import ReplayPage from '@/pages/Replay';

const menuItems: MenuProps['items'] = [
  { key: '/orchestrator', icon: <ApartmentOutlined />, label: '编排器' },
  { key: '/agents', icon: <RobotOutlined />, label: 'Agent 管理' },
  { key: '/capabilities', icon: <ShopOutlined />, label: '能力市场' },
  { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
  { key: '/chatflow', icon: <MessageOutlined />, label: '对话式工作流' },
  { key: '/analytics', icon: <BarChartOutlined />, label: '执行分析' },
  { key: '/prompt-templates', icon: <BulbOutlined />, label: 'Prompt 模板' },
  { key: '/ab-testing', icon: <ExperimentOutlined />, label: 'A/B 测试' },
  { key: '/approvals', icon: <CheckOutlined />, label: '人工审批' },
  { key: '/audit-log', icon: <FileSearchOutlined />, label: '审计日志' },
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/tracer', icon: <EyeOutlined />, label: '任务追踪' },
  { key: '/replay', icon: <HistoryOutlined />, label: '执行回放' },
  { key: '/blackboard', icon: <DatabaseOutlined />, label: '黑板' },
  { key: '/events', icon: <ThunderboltOutlined />, label: '事件流' },
  { key: '/variables', icon: <ShareAltOutlined />, label: '变量管理' },
  { key: '/triggers', icon: <BellOutlined />, label: '触发器' },
  { key: '/llm-config', icon: <CloudServerOutlined />, label: 'LLM 模型' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
];

const { Sider, Content, Header } = Layout;

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const { mode, setMode } = useEngineStore();

  const currentKey = '/' + location.pathname.split('/')[1] || '/orchestrator';

  return (
    <Layout className="hf-layout">
      <Header className="hf-header">
        <div className="hf-header-left">
          <span className="hf-logo">HiveFlow Studio</span>
          <Tag color={mode === 'mock' ? 'orange' : 'green'}>
            {mode === 'mock' ? '模拟模式' : '真实模式'}
          </Tag>
        </div>
        <div className="hf-header-right">
          <RuntimeStatusBar />
          <Switch
            checkedChildren="真实"
            unCheckedChildren="模拟"
            checked={mode === 'real'}
            onChange={(checked) => setMode(checked ? 'real' : 'mock')}
          />
          <WsStatusIndicator />
        </div>
      </Header>
      <Layout className="hf-body">
        <Sider className="hf-sidebar" width={200}>
          <Menu
            mode="inline"
            selectedKeys={[currentKey]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{ borderRight: 0 }}
          />
        </Sider>
        <Content className="hf-content">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<OrchestratorPage />} />
              <Route path="/orchestrator" element={<OrchestratorPage />} />
              <Route path="/agents" element={<AgentsPage />} />
              <Route path="/capabilities" element={<CapabilityMarketPage />} />
              <Route path="/knowledge" element={<KnowledgeBasePage />} />
              <Route path="/chatflow" element={<ChatflowPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/tracer" element={<TracerPage />} />
              <Route path="/replay" element={<ReplayPage />} />
              <Route path="/blackboard" element={<BlackboardPage />} />
              <Route path="/events" element={<EventsPage />} />
              <Route path="/variables" element={<VariablesPage />} />
              <Route path="/triggers" element={<TriggersPage />} />
              <Route path="/prompt-templates" element={<PromptTemplatesPage />} />
              <Route path="/ab-testing" element={<ABTestingPage />} />
              <Route path="/approvals" element={<ApprovalsPage />} />
              <Route path="/audit-log" element={<AuditLogPage />} />
              <Route path="/llm-config" element={<LLMConfigPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </ErrorBoundary>
        </Content>
      </Layout>
    </Layout>
  );
}
