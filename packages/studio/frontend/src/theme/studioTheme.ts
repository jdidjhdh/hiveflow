import type { ThemeConfig } from 'antd';

export const studioTheme: ThemeConfig = {
  token: {
    colorPrimary: '#6366f1',
    colorInfo: '#6366f1',
    colorSuccess: '#10b981',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    borderRadius: 10,
    borderRadiusLG: 14,
    fontFamily:
      "'Inter', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, sans-serif",
    colorBgLayout: '#f1f5f9',
    colorBgContainer: '#ffffff',
    colorBorderSecondary: '#e2e8f0',
    boxShadowSecondary: '0 4px 16px rgba(15, 23, 42, 0.06)',
    controlHeight: 36,
  },
  components: {
    Layout: {
      headerBg: 'transparent',
      siderBg: 'transparent',
      bodyBg: 'transparent',
    },
    Menu: {
      itemBorderRadius: 8,
      itemMarginInline: 8,
      itemHeight: 40,
      iconSize: 16,
      groupTitleFontSize: 11,
      groupTitleColor: '#94a3b8',
    },
    Button: {
      primaryShadow: '0 4px 12px rgba(99, 102, 241, 0.28)',
      defaultShadow: 'none',
    },
    Card: {
      borderRadiusLG: 14,
      boxShadowTertiary: '0 1px 3px rgba(15, 23, 42, 0.06)',
    },
    Tag: {
      borderRadiusSM: 6,
    },
  },
};
