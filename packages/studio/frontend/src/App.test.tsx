import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { App as AntApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';

beforeEach(() => {
  global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  }));
});

describe('App', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <ConfigProvider locale={zhCN}>
          <AntApp>
            <App />
          </AntApp>
        </ConfigProvider>
      </MemoryRouter>,
    );
    const menu = document.querySelector('.ant-menu');
    expect(menu).toBeInTheDocument();
  });
});
