import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import FeatureMaturityTag from '@/components/FeatureMaturityTag';
import PageMaturityNotice from '@/components/PageMaturityNotice';
import { DemoDataBanner } from '@/components/RealModeRequired';
import { useEngineStore } from '@/store/useEngineStore';
import { useLocaleStore } from '@/store/useLocaleStore';

describe('maturity UI components', () => {
  beforeEach(() => {
    useLocaleStore.setState({ locale: 'en' });
    useEngineStore.setState({ mode: 'mock', connected: false, error: null });
  });

  it('FeatureMaturityTag renders beta label in english', () => {
    render(<FeatureMaturityTag maturity="beta" />);
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });

  it('PageMaturityNotice shows demo banner for dashboard in mock mode', () => {
    render(<PageMaturityNotice pageKey="dashboard" />);
    expect(screen.getByText('Demo data')).toBeInTheDocument();
    expect(screen.getByText(/MockEngine/i)).toBeInTheDocument();
  });

  it('DemoDataBanner hidden in real mode', () => {
    useEngineStore.setState({ mode: 'real' });
    const { container } = render(<DemoDataBanner message="test" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('DemoDataBanner visible in mock mode', () => {
    render(<DemoDataBanner message="mock metrics" />);
    expect(screen.getByText('mock metrics')).toBeInTheDocument();
  });
});
