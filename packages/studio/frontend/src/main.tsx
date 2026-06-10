import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider, theme, App as AntApp } from 'antd';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ConfigProvider
        theme={{
          algorithm: theme.defaultAlgorithm,
          token: { colorPrimary: '#6366f1', borderRadius: 8 },
        }}
      >
        <AntApp>
          <App />
        </AntApp>
      </ConfigProvider>
    </BrowserRouter>
  </React.StrictMode>
);