import asyncio
from collections import defaultdict


class MetricsCollector:
    def __init__(self, max_histogram_size: int = 10000):
        self._counters: dict[str, int] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._max_histogram_size = max_histogram_size

    async def increment(self, metric: str, value: int = 1):
        async with self._lock:
            self._counters[metric] = self._counters.get(metric, 0) + value

    async def observe(self, metric: str, value: float):
        async with self._lock:
            self._histograms[metric].append(value)
            # 防止内存泄漏：限制 histogram 大小
            if len(self._histograms[metric]) > self._max_histogram_size:
                self._histograms[metric] = self._histograms[metric][-self._max_histogram_size // 2 :]

    async def snapshot(self) -> dict:
        async with self._lock:
            return {"counters": dict(self._counters), "histograms": {k: list(v) for k, v in self._histograms.items()}}
