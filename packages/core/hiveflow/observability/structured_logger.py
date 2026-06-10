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
import sys
import time
import os
import traceback
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from contextlib import contextmanager


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
                    'name', 'msg', 'args', 'created', 'relativeCreated',
                    'thread', 'threadName', 'process', 'processName',
                    'message', 'exc_info', 'exc_text', 'stack_info',
                    'lineno', 'funcName', 'pathname', 'filename',
                    'module', 'levelno', 'levelname', 'msecs',
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

    def _sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """敏感信息脱敏"""
        sensitive_keys = {'password', 'api_key', 'secret', 'token', 'authorization'}
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
                **self.extra_labels
            )
        else:
            self.logger.info(
                f"Completed {self.operation}",
                operation=self.operation,
                duration=elapsed,
                **self.extra_labels
            )
        return False


def setup_structured_logging(
    level: str = "INFO",
    service: str = "hiveflow",
    output: str = None,
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
        handler = logging.FileHandler(output, encoding='utf-8')
    else:
        handler = logging.StreamHandler(sys.stdout)

    # 设置 JSON 格式化器
    formatter = JSONFormatter(service=service, include_extra=include_extra)
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    # 创建并返回 HiveFlowLogger
    return HiveFlowLogger(root_logger, service=service)
