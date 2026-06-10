import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import PageLoading from '../components/PageLoading';

describe('PageLoading', () => {
  it('renders loading text by default', () => {
    render(<PageLoading />);
    expect(screen.getByText(/加载中/i)).toBeInTheDocument();
  });

  it('renders custom loading text', () => {
    render(<PageLoading text="Custom loading..." />);
    expect(screen.getByText('Custom loading...')).toBeInTheDocument();
  });

  it('renders as fullscreen by default', () => {
    const { container } = render(<PageLoading />);
    const spinner = container.querySelector('.ant-spin');
    expect(spinner).toHaveClass('ant-spin-spinning');
  });

  it('renders as small when size prop is small', () => {
    render(<PageLoading size="small" />);
    expect(screen.getByText(/加载中/i)).toBeInTheDocument();
  });
});
