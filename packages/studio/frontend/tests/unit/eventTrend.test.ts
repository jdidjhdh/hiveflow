import { describe, it, expect, vi, afterEach } from 'vitest';
import { buildEventTrendBuckets } from '@/utils/eventTrend';
import type { EventRecord } from '@/types';

describe('buildEventTrendBuckets', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('aggregates events into time buckets', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-11T12:00:00Z'));

    const nowSec = Date.now() / 1000;
    const events: EventRecord[] = [
      { topic: 'a', timestamp: nowSec - 30, data: {} },
      { topic: 'b', timestamp: nowSec - 90, data: {} },
    ];

    const buckets = buildEventTrendBuckets(events, { bucketMs: 60_000, maxBuckets: 3 });
    expect(buckets).toHaveLength(3);
    expect(buckets.reduce((sum, b) => sum + b.count, 0)).toBe(2);
  });

  it('returns empty counts when no events', () => {
    const buckets = buildEventTrendBuckets([], { maxBuckets: 2 });
    expect(buckets.every((b) => b.count === 0)).toBe(true);
  });
});
