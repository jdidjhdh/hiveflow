import { lazy, Suspense, useMemo, useCallback } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Tag, Switch, Select, Space } from 'antd';
import { useEngineStore } from '@/store/useEngineStore';
import { useI18n } from '@/i18n';
import { buildMenuItems } from '@/config/menuItems';
import { applyStudioModeChange } from '@/engine/syncStudioMode';
import ErrorBoundary from '@/components/ErrorBoundary';
import WsStatusIndicator from '@/components/WsStatusIndicator';
import RuntimeStatusBar from '@/components/RuntimeStatusBar';
import PageLoading from '@/components/PageLoading';

const OrchestratorPage = lazy(() => import('@/pages/Orchestrator'));
const AgentsPage = lazy(() => import('@/pages/Agents'));
const DashboardPage = lazy(() => import('@/pages/Dashboard'));
const TracerPage = lazy(() => import('@/pages/Tracer'));
const BlackboardPage = lazy(() => import('@/pages/Blackboard'));
const EventsPage = lazy(() => import('@/pages/Events'));
const SettingsPage = lazy(() => import('@/pages/Settings'));
const CapabilityMarketPage = lazy(() => import('@/pages/CapabilityMarket'));
const VariablesPage = lazy(() => import('@/pages/Variables'));
const TriggersPage = lazy(() => import('@/pages/Triggers'));
const LLMConfigPage = lazy(() => import('@/pages/LLMConfig'));
const KnowledgeBasePage = lazy(() => import('@/pages/KnowledgeBase'));
const ChatflowPage = lazy(() => import('@/pages/Chatflow'));
const AnalyticsPage = lazy(() => import('@/pages/Analytics'));
const PromptTemplatesPage = lazy(() => import('@/pages/PromptTemplates'));
const ABTestingPage = lazy(() => import('@/pages/ABTesting'));
const AuditLogPage = lazy(() => import('@/pages/AuditLog'));
const ApprovalsPage = lazy(() => import('@/pages/Approvals'));
const ReplayPage = lazy(() => import('@/pages/Replay'));

const { Sider, Content, Header } = Layout;

function LazyPage({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<PageLoading />}>{children}</Suspense>;
}

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const { mode, setMode } = useEngineStore();
  const { t, locale, setLocale } = useI18n();
  const menuItems = useMemo(() => buildMenuItems(t), [t]);

  const currentKey = '/' + (location.pathname.split('/')[1] || 'orchestrator');

  const handleModeChange = useCallback(async (checked: boolean) => {
    const next = checked ? 'real' : 'mock';
    setMode(next);
    await applyStudioModeChange(next);
  }, [setMode]);

  return (
    <Layout className="hf-layout">
      <Header className="hf-header">
        <div className="hf-header-left">
          <span className="hf-logo">{t('app.title')}</span>
          <Tag color={mode === 'mock' ? 'orange' : 'green'}>
            {mode === 'mock' ? t('app.mockMode') : t('app.realMode')}
          </Tag>
        </div>
        <div className="hf-header-right">
          <RuntimeStatusBar />
          <Space size="small">
            <Select
              size="small"
              value={locale}
              onChange={setLocale}
              options={[
                { value: 'zh', label: '中文' },
                { value: 'en', label: 'English' },
              ]}
              style={{ width: 100 }}
              aria-label={t('app.language')}
            />
            <Switch
              data-testid="engine-mode-switch"
              checkedChildren={t('app.realSwitch')}
              unCheckedChildren={t('app.mockSwitch')}
              checked={mode === 'real'}
              onChange={(checked) => { void handleModeChange(checked); }}
            />
          </Space>
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
              <Route path="/" element={<LazyPage><OrchestratorPage /></LazyPage>} />
              <Route path="/orchestrator" element={<LazyPage><OrchestratorPage /></LazyPage>} />
              <Route path="/agents" element={<LazyPage><AgentsPage /></LazyPage>} />
              <Route path="/capabilities" element={<LazyPage><CapabilityMarketPage /></LazyPage>} />
              <Route path="/knowledge" element={<LazyPage><KnowledgeBasePage /></LazyPage>} />
              <Route path="/chatflow" element={<LazyPage><ChatflowPage /></LazyPage>} />
              <Route path="/analytics" element={<LazyPage><AnalyticsPage /></LazyPage>} />
              <Route path="/dashboard" element={<LazyPage><DashboardPage /></LazyPage>} />
              <Route path="/tracer" element={<LazyPage><TracerPage /></LazyPage>} />
              <Route path="/replay" element={<LazyPage><ReplayPage /></LazyPage>} />
              <Route path="/blackboard" element={<LazyPage><BlackboardPage /></LazyPage>} />
              <Route path="/events" element={<LazyPage><EventsPage /></LazyPage>} />
              <Route path="/variables" element={<LazyPage><VariablesPage /></LazyPage>} />
              <Route path="/triggers" element={<LazyPage><TriggersPage /></LazyPage>} />
              <Route path="/prompt-templates" element={<LazyPage><PromptTemplatesPage /></LazyPage>} />
              <Route path="/ab-testing" element={<LazyPage><ABTestingPage /></LazyPage>} />
              <Route path="/approvals" element={<LazyPage><ApprovalsPage /></LazyPage>} />
              <Route path="/audit-log" element={<LazyPage><AuditLogPage /></LazyPage>} />
              <Route path="/llm-config" element={<LazyPage><LLMConfigPage /></LazyPage>} />
              <Route path="/settings" element={<LazyPage><SettingsPage /></LazyPage>} />
            </Routes>
          </ErrorBoundary>
        </Content>
      </Layout>
    </Layout>
  );
}
