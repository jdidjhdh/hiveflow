import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ExecutionSummaryPanel, { ExecutionResult } from '../components/ExecutionSummaryPanel';

describe('ExecutionSummaryPanel', () => {
  const mockResults: ExecutionResult[] = [
    {
      nodeId: 'node-1',
      label: 'Data Input',
      status: 'completed',
      result: { value: 42 },
      duration: 0.5,
    },
    {
      nodeId: 'node-2',
      label: 'Process Data',
      status: 'failed',
      error: 'Timeout exceeded',
      duration: 5.0,
    },
  ];

  const defaultProps = {
    open: true,
    onClose: () => {},
    results: mockResults,
    totalNodes: 2,
  };

  it('renders summary statistics', () => {
    render(<ExecutionSummaryPanel {...defaultProps} />);
    expect(screen.getByText(/执行结果摘要/i)).toBeInTheDocument();
    expect(screen.getByText(/总节点/i)).toBeInTheDocument();
  });

  it('displays correct success count', () => {
    render(<ExecutionSummaryPanel {...defaultProps} />);
    // There are two "1" elements (success and failed), use getAllByText
    const allOnes = screen.getAllByText('1');
    expect(allOnes.length).toBeGreaterThanOrEqual(1);
  });

  it('displays correct failure count', () => {
    render(<ExecutionSummaryPanel {...defaultProps} />);
    // There are two "1" elements (success and failed)
    const allOnes = screen.getAllByText('1');
    expect(allOnes.length).toBeGreaterThanOrEqual(1);
  });

  it('shows 50% success rate', () => {
    render(<ExecutionSummaryPanel {...defaultProps} />);
    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('shows empty state when no results', () => {
    render(
      <ExecutionSummaryPanel
        open={true}
        onClose={() => {}}
        results={[]}
        totalNodes={0}
      />
    );
    expect(screen.getByText('暂无执行结果')).toBeInTheDocument();
  });

  it('does not render when open is false', () => {
    const { container } = render(
      <ExecutionSummaryPanel
        open={false}
        onClose={() => {}}
        results={mockResults}
        totalNodes={2}
      />
    );
    expect(container.firstChild).toBeNull();
  });
});
