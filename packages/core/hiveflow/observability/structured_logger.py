"""HiveFlow Core - 结构化日志

提供 JSON 格式的结构化日志输出，兼容 ELK (Elasticsearch, Logstash, Kibana) 栈。

功能:
- JSON 格式日志，每个字段可独立查询
- 自动添加 trace_id, span_id 用于分布式追踪
- 支持日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- 敏感信息自动脱敏
- 性能指标自动记录

使用方式:
    from hiveflow.observability import setup_structured_logging, HiveFlowLogger

    # 初始化
    logger = setup_structured_logging(level="INFO", service="hiveflow-core")

    # 记录日志
    logger.info("Task started", task_id="task-123", worker_id="worker-1")
    logger.error("Task failed", task_id="task-123", error="timeout", duration=5.2)

    # 或使用上下文管理器自动记录耗时
    with logger.timing("database.query"):
        db.execute("SELECT ...")
"""

import json
import logging
import os
import sys
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""

    def __init__(self, service: str = "hiveflow", include_extra: bool = True):
        super().__init__()
        self.service = service
        self.include_extra = include_extra
        self._hostname = os.environ.get("HOSTNAME", "unknown")
        self._pid = os.getpid()

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service,
            "hostname": self._hostname,
            "pid": self._pid,
            "thread": record.threadName,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加异常信息
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # 添加额外字段
        if self.include_extra:
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in (
                    "name",
                    "msg",
                    "args",
                    "created",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "process",
                    "processName",
                    "message",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                    "lineno",
                    "funcName",
                    "pathname",
                    "filename",
                    "module",
                    "levelno",
                    "levelname",
                    "msecs",
                ):
                    extra_fields[key] = value
            if extra_fields:
                log_entry["extra"] = extra_fields

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class HiveFlowLogger:
    """HiveFlow 自定义日志器，支持结构化日志和性能计时"""

    def __init__(self, logger: logging.Logger, service: str = "hiveflow"):
        self.logger = logger
        self.service = service

    def _log(self, level: int, msg: str, **kwargs):
        """记录日志，支持额外关键字参数"""
        extra = kwargs.copy()

        # 脱敏处理
        extra = self._sanitize(extra)

        self.logger.log(level, msg, extra=extra)

    def _sanitize(self, data: dict[str, Any]) -> dict[str, Any]:
        """敏感信息脱敏"""
        sensitive_keys = {"password", "api_key", "secret", "token", "authorization"}
        sanitized = {}

        for key, value in data.items():
            if key.lower() in sensitive_keys:
                sanitized[key] = "****REDACTED****"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize(value)
            else:
                sanitized[key] = value

        return sanitized

    def debug(self, msg: str, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)

    def warn(self, msg: str, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        self._log(logging.CRITICAL, msg, **kwargs)

    def exception(self, msg: str, **kwargs):
        """记录异常日志，自动包含 traceback"""
        self._log(logging.ERROR, msg, exc_info=True, **kwargs)

    @contextmanager
    def timing(self, operation: str, **extra_labels):
        """上下文管理器，自动记录操作耗时

        with logger.timing("database.query", db="main"):
            db.execute("SELECT ...")
        """
        start_time = time.perf_counter()
        self.debug(f"Starting {operation}", operation=operation, **extra_labels)

        try:
            yield
            elapsed = time.perf_counter() - start_time
            self.info(f"Completed {operation}", operation=operation, duration=elapsed, **extra_labels)
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.exception(f"Failed {operation}", operation=operation, duration=elapsed, error=str(e), **extra_labels)
            raise

    async def async_timing(self, operation: str, **extra_labels):
        """异步版本的 timing (用于需要 await 的场景)

        使用方式:
            async with logger.async_timing("api.call"):
                await api.call()
        """
        return _AsyncTimingContext(self, operation, extra_labels)


class _AsyncTimingContext:
    """异步 timing 上下文管理器"""

    def __init__(self, logger: HiveFlowLogger, operation: str, extra_labels: dict):
        self.logger = logger
        self.operation = operation
        self.extra_labels = extra_labels
        self.start_time = None

    async def __aenter__(self):
        self.start_time = time.perf_counter()
        self.logger.debug(f"Starting {self.operation}", operation=self.operation, **self.extra_labels)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.perf_counter() - self.start_time
        if exc_type is not None:
            self.logger.exception(
                f"Failed {self.operation}",
                operation=self.operation,
                duration=elapsed,
                error=str(exc_val),
                **self.extra_labels,
            )
        else:
            self.logger.info(
                f"Completed {self.operation}", operation=self.operation, duration=elapsed, **self.extra_labels
            )
        return False


def setup_structured_logging(
    level: str = "INFO",
    service: str = "hiveflow",
    output: str | None = None,
    include_extra: bool = True,
) -> HiveFlowLogger:
    """配置结构化日志

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        service: 服务名称，用于标识日志来源
        output: 输出目标 (None=stdout, 或文件路径)
        include_extra: 是否包含额外的日志字段

    Returns:
        HiveFlowLogger 实例
    """
    # 创建根日志器
    root_logger = logging.getLogger("hiveflow")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除已有的处理器
    root_logger.handlers.clear()

    # 创建处理器
    if output:
        handler = logging.FileHandler(output, encoding="utf-8")
    else:
        handler = logging.StreamHandler(sys.stdout)

    # 设置 JSON 格式化器
    formatter = JSONFormatter(service=service, include_extra=include_extra)
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    # 创建并返回 HiveFlowLogger
    return HiveFlowLogger(root_logger, service=service)


class SlidingWindowCounter:
    """滑动窗口计数器，用于速率限制检测"""

    def __init__(self, window_size: float = 1.0, max_samples: int = 1000):
        """
        Args:
            window_size: 窗口大小（秒），默认1秒
            max_samples: 最大样本数，防止内存无限增长
        """
        self.window_size = window_size
        self.max_samples = max_samples
        self._timestamps: deque[float] = deque()

    def add(self) -> int:
        """添加一个事件，返回当前窗口内的计数"""
        now = time.time()
        # 添加当前时间戳
        self._timestamps.append(now)

        # 清理过期的时间戳（超出窗口大小）
        cutoff = now - self.window_size
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

        # 防止内存无限增长
        if len(self._timestamps) > self.max_samples:
            # 保留最新的样本
            while len(self._timestamps) > self.max_samples:
                self._timestamps.popleft()

        return len(self._timestamps)

    def count(self) -> int:
        """获取当前窗口内的计数（不添加新事件）"""
        now = time.time()
        cutoff = now - self.window_size
        # 清理过期的时间戳
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        return len(self._timestamps)

    def reset(self) -> None:
        """重置计数器"""
        self._timestamps.clear()


class RateLimitedLogger:
    """
    速率限制日志器

    功能:
    - 高频日志（>100条/秒）启用采样（每10条记录1条）
    - 使用滑动窗口计数器检测速率
    - 支持按日志级别独立控制

    使用方式:
        logger = RateLimitedLogger(base_logger, rate_limit=100, sample_rate=10)
        if logger.should_log("INFO"):
            logger.info("message")
    """

    # 默认配置
    DEFAULT_RATE_LIMIT = 100  # 每秒最大日志数
    DEFAULT_SAMPLE_RATE = 10  # 采样率（每N条记录1条）
    DEFAULT_WINDOW_SIZE = 1.0  # 滑动窗口大小（秒）

    def __init__(
        self,
        base_logger: HiveFlowLogger | logging.Logger,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        window_size: float = DEFAULT_WINDOW_SIZE,
    ):
        """
        Args:
            base_logger: 基础日志器（HiveFlowLogger 或标准 Logger）
            rate_limit: 每秒最大日志数阈值，超过后启用采样
            sample_rate: 采样率，每N条记录1条
            window_size: 滑动窗口大小（秒）
        """
        self._base_logger = base_logger
        self.rate_limit = rate_limit
        self.sample_rate = sample_rate
        self.window_size = window_size

        # 每个日志级别的计数器
        self._counters: dict[str, SlidingWindowCounter] = {}
        # 采样计数器（用于采样时计数）
        self._sample_counters: dict[str, int] = {}
        # 是否处于采样模式
        self._sampling_mode: dict[str, bool] = {}

    def _get_counter(self, level: str) -> SlidingWindowCounter:
        """获取指定级别的计数器"""
        if level not in self._counters:
            self._counters[level] = SlidingWindowCounter(window_size=self.window_size)
        return self._counters[level]

    def should_log(self, level: str) -> bool:
        """
        判断是否应该记录日志

        Args:
            level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）

        Returns:
            True 表示应该记录，False 表示应该跳过
        """
        counter = self._get_counter(level)
        current_count = counter.add()

        # 检查是否超过速率限制
        if current_count > self.rate_limit:
            # 进入采样模式
            if level not in self._sampling_mode or not self._sampling_mode[level]:
                self._sampling_mode[level] = True
                self._sample_counters[level] = 0
                # 记录采样模式开启警告
                self._log_warning(
                    f"Log rate limit exceeded for {level} level. "
                    f"Current rate: {current_count}/s. Sampling enabled (1/{self.sample_rate})."
                )

            # 采样逻辑：每 sample_rate 条记录1条
            self._sample_counters[level] += 1
            if self._sample_counters[level] % self.sample_rate == 0:
                return True
            return False
        else:
            # 未超过速率限制，正常记录
            # 如果之前处于采样模式，现在恢复正常
            if level in self._sampling_mode and self._sampling_mode[level]:
                self._sampling_mode[level] = False
                self._log_warning(
                    f"Log rate normalized for {level} level. Sampling disabled."
                )
            return True

    def _log_warning(self, msg: str) -> None:
        """记录警告日志（不经过速率限制检查）"""
        if isinstance(self._base_logger, HiveFlowLogger):
            self._base_logger.warning(msg, rate_limit_event=True)
        else:
            self._base_logger.warning(msg)

    def _log(self, level: int, level_name: str, msg: str, **kwargs):
        """记录日志（带速率限制检查）"""
        if self.should_log(level_name):
            if isinstance(self._base_logger, HiveFlowLogger):
                self._base_logger._log(level, msg, sampled=level_name in self._sampling_mode, **kwargs)
            else:
                extra = kwargs.copy()
                extra["sampled"] = level_name in self._sampling_mode
                self._base_logger.log(level, msg, extra=extra)

    def debug(self, msg: str, **kwargs):
        self._log(logging.DEBUG, "DEBUG", msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._log(logging.INFO, "INFO", msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log(logging.WARNING, "WARNING", msg, **kwargs)

    def warn(self, msg: str, **kwargs):
        self._log(logging.WARNING, "WARNING", msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log(logging.ERROR, "ERROR", msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        self._log(logging.CRITICAL, "CRITICAL", msg, **kwargs)

    def exception(self, msg: str, **kwargs):
        """记录异常日志，自动包含 traceback"""
        if self.should_log("ERROR"):
            if isinstance(self._base_logger, HiveFlowLogger):
                self._base_logger._log(logging.ERROR, msg, exc_info=True, **kwargs)
            else:
                extra = kwargs.copy()
                extra["exc_info"] = True
                self._base_logger.log(logging.ERROR, msg, extra=extra)

    @contextmanager
    def timing(self, operation: str, **extra_labels):
        """上下文管理器，自动记录操作耗时"""
        start_time = time.perf_counter()
        self.debug(f"Starting {operation}", operation=operation, **extra_labels)

        try:
            yield
            elapsed = time.perf_counter() - start_time
            self.info(f"Completed {operation}", operation=operation, duration=elapsed, **extra_labels)
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.exception(f"Failed {operation}", operation=operation, duration=elapsed, error=str(e), **extra_labels)
            raise

    def get_stats(self) -> dict[str, Any]:
        """获取速率限制统计信息"""
        stats = {
            "rate_limit": self.rate_limit,
            "sample_rate": self.sample_rate,
            "window_size": self.window_size,
            "levels": {},
        }
        for level, counter in self._counters.items():
            stats["levels"][level] = {
                "current_rate": counter.count(),
                "sampling_mode": self._sampling_mode.get(level, False),
                "sample_counter": self._sample_counters.get(level, 0),
            }
        return stats

    def reset(self) -> None:
        """重置所有计数器和采样状态"""
        for counter in self._counters.values():
            counter.reset()
        self._sample_counters.clear()
        self._sampling_mode.clear()


def setup_rate_limited_logging(
    level: str = "INFO",
    service: str = "hiveflow",
    output: str | None = None,
    include_extra: bool = True,
    rate_limit: int = RateLimitedLogger.DEFAULT_RATE_LIMIT,
    sample_rate: int = RateLimitedLogger.DEFAULT_SAMPLE_RATE,
    window_size: float = RateLimitedLogger.DEFAULT_WINDOW_SIZE,
) -> RateLimitedLogger:
    """
    配置带速率限制的结构化日志

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        service: 服务名称
        output: 输出目标 (None=stdout, 或文件路径)
        include_extra: 是否包含额外的日志字段
        rate_limit: 每秒最大日志数阈值
        sample_rate: 采样率
        window_size: 滑动窗口大小（秒）

    Returns:
        RateLimitedLogger 实例
    """
    base_logger = setup_structured_logging(level=level, service=service, output=output, include_extra=include_extra)
    return RateLimitedLogger(base_logger, rate_limit=rate_limit, sample_rate=sample_rate, window_size=window_size)
