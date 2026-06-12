import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import enUS from 'antd/locale/en_US';
import App from './App';
import { useLocaleStore } from '@/store/useLocaleStore';
import { studioTheme } from '@/theme/studioTheme';
import './index.css';

function Root() {
  const locale = useLocaleStore((s) => s.locale);
  return (
    <ConfigProvider locale={locale === 'zh' ? zhCN : enUS} theme={studioTheme}>
      <AntApp>
        <App />
      </AntApp>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Root />
    </BrowserRouter>
  </React.StrictMode>,
);
