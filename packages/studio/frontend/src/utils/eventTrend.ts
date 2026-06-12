import type { EventRecord } from '@/types';

export interface EventTrendBucket {
  label: string;
  count: number;
}

/** 将事件按固定时间窗口聚合，用于 Dashboard 事件趋势图 */
export function buildEventTrendBuckets(
  events: EventRecord[],
  options?: { bucketMs?: number; maxBuckets?: number },
): EventTrendBucket[] {
  const bucketMs = options?.bucketMs ?? 60_000;
  const maxBuckets = options?.maxBuckets ?? 12;
  const now = Date.now();
  const buckets: EventTrendBucket[] = [];

  for (let i = maxBuckets - 1; i >= 0; i--) {
    const start = now - (i + 1) * bucketMs;
    const end = now - i * bucketMs;
    const label = new Date(end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const count = events.filter((e) => {
      const ts = e.timestamp * 1000;
      return ts >= start && ts < end;
    }).length;
    buckets.push({ label, count });
  }

  return buckets;
}
