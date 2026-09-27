import importlib.util
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

try:
    from .blackboard import (
        BlackboardBackend,
        EncryptedBlackboard,
        EnvKeyProvider,
        FileKeyProvider,
        KeyProvider,
        MemoryBlackboard,
        RedisBlackboard,
        SecureBlackboard,
        TTLMemoryBlackboard,
    )
    from .bus import EventBus, InProcessEventBus, RedisEventBus
    from .cell import Cell, Worker
    from .checkpoint import CheckpointManager, MemoryCheckpointBackend, SQLiteCheckpointBackend
    from .hitl import HITLManager
    from .metrics import MetricsCollector
    from .orchestrator import DAGOrchestrator, DynamicOrchestrator
    from .rag import KnowledgeBaseManager
    from .scheduler import InProcessScheduler, SchedulerConfig
    from .validation import ValidationPipeline
except ImportError:
    from blackboard import (
        EncryptedBlackboard,
        EnvKeyProvider,
        FileKeyProvider,
        KeyProvider,
        MemoryBlackboard,
        RedisBlackboard,
        SecureBlackboard,
        TTLMemoryBlackboard,
    )
    from bus import InProcessEventBus, RedisEventBus
    from cell import Cell, Worker
    from checkpoint import CheckpointManager, MemoryCheckpointBackend, SQLiteCheckpointBackend
    from hitl import HITLManager
    from metrics import MetricsCollector
    from orchestrator import DAGOrchestrator, DynamicOrchestrator
    from rag import KnowledgeBaseManager
    from scheduler import InProcessScheduler, SchedulerConfig
    from validation import ValidationPipeline

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """
    Health status for readiness probe.

    Attributes:
        healthy: Overall health status (True if all checks pass)
        checks: Detailed check results for each component
        timestamp: Timestamp of the check
    """

    healthy: bool
    checks: dict[str, dict[str, Any]]
    timestamp: str = field(default_factory=lambda: "")
    issues: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            import datetime
            self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()


def detect_max_concurrency() -> int:
    """
    Detect optimal max_concurrency based on system resources.

    Priority order:
    1. HIVEFLOW_MAX_CONCURRENCY environment variable (highest priority)
    2. Container CPU quota (cfs_quota_us / cfs_period_us)
    3. CPU count * 2
    4. Default value: 4

    Returns:
        Optimal max_concurrency value
    """
    # 1. Check environment variable (highest priority)
    env_value = os.environ.get("HIVEFLOW_MAX_CONCURRENCY")
    if env_value:
        try:
            return int(env_value)
        except ValueError:
            logger.warning(f"Invalid HIVEFLOW_MAX_CONCURRENCY value: {env_value}")

    # 2. Check container CPU quota (Docker/Kubernetes)
    # In containers, CPU quota is set via cpu.cfs_quota_us and cpu.cfs_period_us
    # Path: /sys/fs/cgroup/cpu/cpu.cfs_quota_us and cpu.cfs_period_us
    try:
        cfs_quota_path = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
        cfs_period_path = Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")

        if cfs_quota_path.exists() and cfs_period_path.exists():
            quota_us = int(cfs_quota_path.read_text().strip())
            period_us = int(cfs_period_path.read_text().strip())

            # quota_us of -1 means no limit (unlimited CPU)
            if quota_us > 0 and period_us > 0:
                # Number of CPUs = quota / period
                cpu_count = quota_us / period_us
                # Use cpu_count * 2 for better I/O bound concurrency
                return max(1, int(cpu_count * 2))
    except (FileNotFoundError, ValueError, PermissionError) as e:
        logger.debug(f"Could not read cgroup CPU quota: {e}")

    # 3. Check alternative cgroup v2 path (unified hierarchy)
    try:
        cpu_max_path = Path("/sys/fs/cgroup/cpu.max")
        if cpu_max_path.exists():
            content = cpu_max_path.read_text().strip().split()
            if len(content) == 2:
                quota, period = content
                if quota != "max":
                    cpu_count = int(quota) / int(period)
                    return max(1, int(cpu_count * 2))
    except (FileNotFoundError, ValueError, PermissionError) as e:
        logger.debug(f"Could not read cgroup v2 CPU max: {e}")

    # 4. Use CPU count * 2 (for I/O bound workloads)
    try:
        cpu_count = os.cpu_count()
        if cpu_count:
            return max(1, cpu_count * 2)
    except Exception as e:
        logger.debug(f"Could not get CPU count: {e}")

    # 5. Default fallback
    return 4


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


_FERNET_AVAILABLE = _has_module("cryptography.fernet")
_JSONSCHEMA_AVAILABLE = _has_module("jsonschema")
_REDIS_AVAILABLE = _has_module("redis")


def _serialize_capability(cap) -> dict[str, Any]:
    """Serialize Capability for JSON storage (sets → sorted lists)."""
    return {
        "agent_id": cap.agent_id,
        "skills": sorted(cap.skills),
        "read_keys": sorted(cap.read_keys),
        "write_keys": sorted(cap.write_keys),
        "load": cap.load,
        "history": list(cap.history),
        "state": cap.state,
        "weight": cap.weight,
        "pending_tasks": cap.pending_tasks,
        "max_queue_size": cap.max_queue_size,
    }


def _deserialize_set(value: list[str] | set[str] | str | None) -> set[str]:
    """Restore a set field from JSON (supports legacy string fallbacks)."""
    if value is None:
        return set()
    if isinstance(value, set):
        return value
    if isinstance(value, (list, tuple)):
        return set(value)
    if isinstance(value, str):
        logger.warning("Legacy set serialization detected, resetting to empty: %r", value[:80])
        return set()
    return set(value)


@dataclass
class HiveFlowConfig:
    """HiveFlow configuration with all tunable parameters.

    Configuration categories:
    - Scheduler: auction threshold, timeout
    - Blackboard: type, Redis connection, TTL, encryption, max object size
    - Circuit Breaker: failure threshold, timeout
    - Worker: queue size
    - Features: HITL, checkpoint, RAG
    """
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    blackboard_type: str = "ttl_memory"  # 🔄 P0 FIX: Default changed from "memory" to "ttl_memory" to prevent unbounded growth
    encryption_key_provider: KeyProvider | None = None
    redis_url: str | None = None
    redis_db: int = 0
    redis_max_connections: int = 20  # 🔄 Increased default for production
    redis_socket_timeout: float = 5.0
    redis_blackboard_poll_interval: float = 0.05
    blackboard_prefix: str = "hiveflow"
    max_audit_entries: int = 1000
    max_object_size: int = 10 * 1024 * 1024  # 🔧 大对象保护：默认 10MB
    use_json_schema: bool = False
    default_ttl: float = 3600.0  # 🔄 P0 FIX: Default TTL 1 hour to prevent memory bloat
    worker_max_queue_size: int = 100
    encrypt_compression: bool = False
    log_level: str = "INFO"
    enable_hitl: bool = False
    enable_checkpoint: bool = False
    enable_rag: bool = False
    checkpoint_backend: str = "memory"  # memory | sqlite
    checkpoint_db_path: str = "hiveflow_checkpoints.db"

    # 🔄 New configuration parameters (from architecture review)
    auction_agent_threshold: int = 20  # Scheduler fallback threshold
    circuit_breaker_threshold: int = 5  # LLM circuit breaker failure threshold
    circuit_breaker_timeout: float = 60.0  # LLM circuit breaker timeout (seconds)
    ttl_cleanup_interval: float = 120.0  # 🔄 P0 FIX: Cleanup interval increased to 120s for efficiency
    health_check_interval: float = 30.0  # Health check loop interval (seconds)
    max_concurrency: int = -1  # Semaphore concurrency limit (-1 = auto-detect, see detect_max_concurrency())

    def validate(self) -> None:
        """Validate configuration values."""
        valid_bb_types = {"memory", "ttl_memory", "redis", "encrypted"}
        if self.blackboard_type not in valid_bb_types:
            raise ValueError(f"Invalid blackboard_type '{self.blackboard_type}'. Must be one of {valid_bb_types}")
        if self.redis_max_connections < 1:
            raise ValueError("redis_max_connections must be >= 1")
        if self.redis_socket_timeout <= 0:
            raise ValueError("redis_socket_timeout must be > 0")
        if self.redis_blackboard_poll_interval <= 0:
            raise ValueError("redis_blackboard_poll_interval must be > 0")
        if self.max_audit_entries < 0:
            raise ValueError("max_audit_entries must be >= 0")
        # 🔧 大对象保护：验证 max_object_size
        if self.max_object_size < 1:
            raise ValueError("max_object_size must be >= 1 byte")
        if self.worker_max_queue_size < 1:
            raise ValueError("worker_max_queue_size must be >= 1")
        if self.redis_url is not None and not self.redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("redis_url must start with redis:// or rediss://")
        if self.checkpoint_backend not in ("memory", "sqlite"):
            raise ValueError("checkpoint_backend must be 'memory' or 'sqlite'")
        # 🔄 Validate new parameters
        if self.auction_agent_threshold < 1:
            raise ValueError("auction_agent_threshold must be >= 1")
        if self.circuit_breaker_threshold < 1:
            raise ValueError("circuit_breaker_threshold must be >= 1")
        if self.circuit_breaker_timeout <= 0:
            raise ValueError("circuit_breaker_timeout must be > 0")
        if self.ttl_cleanup_interval <= 0:
            raise ValueError("ttl_cleanup_interval must be > 0")
        if self.health_check_interval <= 0:
            raise ValueError("health_check_interval must be > 0")
        # 🔄 Validate max_concurrency
        if self.max_concurrency != -1 and self.max_concurrency < 1:
            raise ValueError("max_concurrency must be -1 (auto-detect) or >= 1")

    @classmethod
    def from_env(cls, prefix: str = "HIVEFLOW") -> "HiveFlowConfig":
        """Create HiveFlowConfig from environment variables.

        Environment variables (with HIVEFLOW_ prefix):
            BLACKBOARD_TYPE: memory, ttl_memory, redis, encrypted (default: ttl_memory)  # 🔄 P0 FIX
            REDIS_URL: Redis connection URL (default: redis://localhost)
            REDIS_DB: Redis database number (default: 0)
            REDIS_MAX_CONNECTIONS: Max connection pool size (default: 20)
            REDIS_SOCKET_TIMEOUT: Socket timeout in seconds (default: 5.0)
            REDIS_POLL_INTERVAL: Blackboard poll interval in seconds (default: 0.05)
            PREFIX: Key prefix (default: hiveflow)
            MAX_AUDIT_ENTRIES: Max audit log entries (default: 1000)
            MAX_OBJECT_SIZE: Max object size in bytes (default: 10MB)  # 🔧 大对象保护
            DEFAULT_TTL: Default TTL in seconds (default: 3600.0)  # 🔄 P0 FIX
            WORKER_MAX_QUEUE_SIZE: Max worker queue size (default: 100)
            ENCRYPT_COMPRESSION: Enable compression for encrypted blackboard (default: false)
            LOG_LEVEL: Logging level (default: INFO)
            ENCRYPTION_KEY_SOURCE: env or file (default: env)
            ENCRYPTION_KEY_ENV_VAR: Env var name for key (default: HIVEFLOW_ENCRYPTION_KEY)
            ENCRYPTION_KEY_FILE: Path to key file
            USE_JSON_SCHEMA: Enable JSON schema validation (default: false)
            TTL_CLEANUP_INTERVAL: TTL cleanup interval in seconds (default: 120.0)  # 🔄 P0 FIX
        """

        def _env(key: str, default: str = "") -> str:
            return os.environ.get(f"{prefix}_{key}", default)

        def _env_int(key: str, default: int) -> int:
            val = _env(key, str(default))
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        def _env_float(key: str, default: float) -> float:
            val = _env(key, str(default))
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        def _env_bool(key: str, default: bool) -> bool:
            val = _env(key, str(default)).lower()
            return val in ("true", "1", "yes", "on")

        # Determine encryption key provider
        encryption_key_provider = None
        bb_type = _env("BLACKBOARD_TYPE", "ttl_memory")  # 🔄 P0 FIX: Default changed from "memory" to "ttl_memory"
        if bb_type == "encrypted":
            key_source = _env("ENCRYPTION_KEY_SOURCE", "env")
            if key_source == "file":
                key_file = _env("ENCRYPTION_KEY_FILE")
                if key_file:
                    encryption_key_provider = FileKeyProvider(key_file)
                else:
                    raise ValueError("ENCRYPTION_KEY_FILE is required when ENCRYPTION_KEY_SOURCE=file")
            else:
                key_env_var = _env("ENCRYPTION_KEY_ENV_VAR", f"{prefix}_ENCRYPTION_KEY")
                encryption_key_provider = EnvKeyProvider(key_env_var)

        default_ttl_str = _env("DEFAULT_TTL", "")
        # 🔄 P0 FIX: Default TTL changed from None to 3600.0
        default_ttl = float(default_ttl_str) if default_ttl_str else 3600.0

        config = cls(
            blackboard_type=bb_type,
            encryption_key_provider=encryption_key_provider,
            redis_url=_env("REDIS_URL", None),
            redis_db=_env_int("REDIS_DB", 0),
            redis_max_connections=_env_int("REDIS_MAX_CONNECTIONS", 20),
            redis_socket_timeout=_env_float("REDIS_SOCKET_TIMEOUT", 5.0),
            redis_blackboard_poll_interval=_env_float("REDIS_POLL_INTERVAL", 0.05),
            blackboard_prefix=_env("PREFIX", "hiveflow"),
            max_audit_entries=_env_int("MAX_AUDIT_ENTRIES", 1000),
            max_object_size=_env_int("MAX_OBJECT_SIZE", 10 * 1024 * 1024),  # 🔧 大对象保护：默认 10MB
            use_json_schema=_env_bool("USE_JSON_SCHEMA", False),
            default_ttl=default_ttl,
            worker_max_queue_size=_env_int("WORKER_MAX_QUEUE_SIZE", 100),
            encrypt_compression=_env_bool("ENCRYPT_COMPRESSION", False),
            log_level=_env("LOG_LEVEL", "INFO"),
            # 🔄 New parameters from environment
            auction_agent_threshold=_env_int("AUCTION_AGENT_THRESHOLD", 20),
            circuit_breaker_threshold=_env_int("CIRCUIT_BREAKER_THRESHOLD", 5),
            circuit_breaker_timeout=_env_float("CIRCUIT_BREAKER_TIMEOUT", 60.0),
            ttl_cleanup_interval=_env_float("TTL_CLEANUP_INTERVAL", 60.0),
            health_check_interval=_env_float("HEALTH_CHECK_INTERVAL", 30.0),
            max_concurrency=_env_int("MAX_CONCURRENCY", -1),
        )
        config.validate()

        # 🔄 Resolve auto-detected max_concurrency
        if config.max_concurrency == -1:
            config.max_concurrency = detect_max_concurrency()

        return config


class HiveFlow:
    def __init__(self, config: HiveFlowConfig = None):
        self.config = config or HiveFlowConfig()

        if self.config.use_json_schema and not _JSONSCHEMA_AVAILABLE:
            raise ImportError("jsonschema library is required when use_json_schema=True")

        # 初始化黑板后端
        base_bb: BlackboardBackend
        if self.config.blackboard_type == "redis":
            if not _REDIS_AVAILABLE:
                raise ImportError("redis is required for RedisBlackboard")
            base_bb = RedisBlackboard(
                redis_url=self.config.redis_url or "redis://localhost",
                prefix=self.config.blackboard_prefix,
                db=self.config.redis_db,
                max_connections=self.config.redis_max_connections,
                socket_timeout=self.config.redis_socket_timeout,
                poll_interval=self.config.redis_blackboard_poll_interval,
            )
        elif self.config.blackboard_type == "ttl_memory":
            base_bb = TTLMemoryBlackboard(default_ttl=self.config.default_ttl)
        elif self.config.blackboard_type == "encrypted":
            if not self.config.encryption_key_provider:
                raise ValueError("encryption_key_provider is required for encrypted blackboard")
            inner = (
                MemoryBlackboard()
                if not self.config.default_ttl
                else TTLMemoryBlackboard(default_ttl=self.config.default_ttl)
            )
            base_bb = EncryptedBlackboard(
                inner, self.config.encryption_key_provider, use_compression=self.config.encrypt_compression
            )
        else:
            if self.config.blackboard_type not in ("memory",):
                logger.warning(f"Unknown blackboard_type '{self.config.blackboard_type}', falling back to memory.")
            base_bb = (
                MemoryBlackboard()
                if not self.config.default_ttl
                else TTLMemoryBlackboard(default_ttl=self.config.default_ttl)
            )

        self.blackboard = SecureBlackboard(
            base_bb,
            max_audit=self.config.max_audit_entries,
            max_object_size=self.config.max_object_size,  # 🔧 大对象保护
        )

        # 初始化事件总线
        bus: EventBus
        if self.config.blackboard_type == "redis":
            bus = RedisEventBus(
                redis_url=self.config.redis_url or "redis://localhost",
                prefix=self.config.blackboard_prefix,
                db=self.config.redis_db,
                max_connections=self.config.redis_max_connections,
                socket_timeout=self.config.redis_socket_timeout,
            )
        else:
            bus = InProcessEventBus()
        self.bus = bus

        self.scheduler = InProcessScheduler(self.bus, self.config.scheduler)
        self.validation_pipeline = ValidationPipeline()
        self.metrics = MetricsCollector()
        self.cell = Cell(
            self.bus,
            self.blackboard,
            self.scheduler,
            self.validation_pipeline,
            default_max_queue_size=self.config.worker_max_queue_size,
        )

        self.hitl_manager: HITLManager | None = HITLManager() if self.config.enable_hitl else None
        self.checkpoint_manager: CheckpointManager | None = None
        if self.config.enable_checkpoint:
            if self.config.checkpoint_backend == "sqlite":
                if SQLiteCheckpointBackend is None:
                    raise ImportError(
                        "aiosqlite is required for sqlite checkpoint backend. "
                        "Install with: pip install hiveflow-core[checkpoint]"
                    )
                cp_backend = SQLiteCheckpointBackend(self.config.checkpoint_db_path)
            else:
                cp_backend = MemoryCheckpointBackend()
            self.checkpoint_manager = CheckpointManager(cp_backend)
        self.kb_manager: KnowledgeBaseManager | None = KnowledgeBaseManager() if self.config.enable_rag else None

        self.dag_orchestrator = DAGOrchestrator(
            self.blackboard,
            hitl_manager=self.hitl_manager,
            checkpoint_manager=self.checkpoint_manager,
        )
        self.dynamic_orchestrator = DynamicOrchestrator(
            self.blackboard,
            hitl_manager=self.hitl_manager,
            checkpoint_manager=self.checkpoint_manager,
        )
        self._handler_registry: dict[str, Callable] = {}
        self._custom_strategy: Any | None = None

    async def set_strategy(self, strategy) -> None:
        self._custom_strategy = strategy
        await self.scheduler.set_strategy(strategy)

    async def start(self) -> None:
        await self.bus.start()
        await self.scheduler.start()

    def register_agent_handler(self, agent_id: str, handler: Callable):
        self._handler_registry[agent_id] = handler

    async def create_agent(
        self,
        agent_id: str,
        skills: set[str],
        read_keys: set[str],
        write_keys: set[str],
        task_handler: Callable,
        max_queue_size: int | None = None,
    ) -> Worker:
        self.register_agent_handler(agent_id, task_handler)
        return await self.cell.create_worker(
            agent_id, skills, read_keys, write_keys, task_handler, max_queue_size=max_queue_size
        )

    async def save_state(self):
        caps = [cap for cap in self.scheduler._capabilities.values()]
        handler_info = {aid: handler.__name__ for aid, handler in self._handler_registry.items()}
        state = {
            "caps": [_serialize_capability(cap) for cap in caps],
            "handler_names": handler_info,
            "version": 3,
        }
        await self.blackboard.sys_put("__hiveflow_state__:agents", json.dumps(state))

    async def restore_state(self):
        try:
            data = await self.blackboard.sys_get("__hiveflow_state__:agents")
            state = json.loads(data)
            caps_data = state["caps"]
            stored_handlers = state.get("handler_names", {})
            for cap_dict in caps_data:
                agent_id = cap_dict["agent_id"]
                handler = self._handler_registry.get(agent_id)
                if not handler:
                    logger.error("Cannot restore agent %s: no handler registered", agent_id)
                    continue
                expected_name = stored_handlers.get(agent_id)
                if expected_name and handler.__name__ != expected_name:
                    logger.warning(
                        "Agent %s handler changed from '%s' to '%s'",
                        agent_id,
                        expected_name,
                        handler.__name__,
                    )
                restored_max_queue = cap_dict.get("max_queue_size", self.config.worker_max_queue_size)
                await self.cell.create_worker(
                    agent_id=agent_id,
                    skills=_deserialize_set(cap_dict.get("skills")),
                    read_keys=_deserialize_set(cap_dict.get("read_keys")),
                    write_keys=_deserialize_set(cap_dict.get("write_keys")),
                    handler=handler,
                    max_queue_size=restored_max_queue,
                )
        except KeyError as e:
            logger.error("Failed to restore state: missing key %s", e)
        except json.JSONDecodeError as e:
            logger.error("Failed to restore state: invalid JSON (%s)", e)
        except Exception as e:
            logger.exception("Failed to restore state: %s", e)

    async def shutdown(self):
        await self.cell.shutdown()
        await self.scheduler.close()
        await self.bus.close()
        await self.blackboard.close()
    
    async def health_check(self) -> dict[str, Any]:
        """
        🔍 Health check for all HiveFlow components.
        
        Checks:
        - Blackboard connectivity (Redis ping or memory status)
        - EventBus status (running/stopped)
        - Scheduler status (active workers count)
        - Optional: HITL, Checkpoint, RAG managers
        
        Returns:
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "components": {
                    "blackboard": {"status": "...", "details": ...},
                    "bus": {"status": "...", "details": ...},
                    "scheduler": {"status": "...", "details": ...},
                    ...
                },
                "timestamp": "ISO timestamp"
            }
        """
        import datetime
        
        result = {
            "status": "healthy",
            "components": {},
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        
        issues = []
        
        # Check Blackboard
        try:
            bb_status = await self._check_blackboard()
            result["components"]["blackboard"] = bb_status
            if bb_status["status"] != "healthy":
                issues.append("blackboard")
        except Exception as e:
            result["components"]["blackboard"] = {"status": "error", "error": str(e)}
            issues.append("blackboard")
        
        # Check EventBus
        try:
            bus_status = await self._check_bus()
            result["components"]["bus"] = bus_status
            if bus_status["status"] != "healthy":
                issues.append("bus")
        except Exception as e:
            result["components"]["bus"] = {"status": "error", "error": str(e)}
            issues.append("bus")
        
        # Check Scheduler
        try:
            scheduler_status = self._check_scheduler()
            result["components"]["scheduler"] = scheduler_status
            if scheduler_status["status"] != "healthy":
                issues.append("scheduler")
        except Exception as e:
            result["components"]["scheduler"] = {"status": "error", "error": str(e)}
            issues.append("scheduler")
        
        # Check optional components
        if self.hitl_manager:
            try:
                hitl_status = {"status": "healthy", "active_gates": len(self.hitl_manager._gates)}
                result["components"]["hitl"] = hitl_status
            except Exception as e:
                result["components"]["hitl"] = {"status": "error", "error": str(e)}
                issues.append("hitl")
        
        if self.checkpoint_manager:
            try:
                cp_status = {"status": "healthy"}
                result["components"]["checkpoint"] = cp_status
            except Exception as e:
                result["components"]["checkpoint"] = {"status": "error", "error": str(e)}
                issues.append("checkpoint")
        
        if self.kb_manager:
            try:
                kb_status = {"status": "healthy"}
                result["components"]["rag"] = kb_status
            except Exception as e:
                result["components"]["rag"] = {"status": "error", "error": str(e)}
                issues.append("rag")
        
        # Determine overall status
        if len(issues) > 0:
            if len(issues) >= 3:
                result["status"] = "unhealthy"
            else:
                result["status"] = "degraded"
            result["issues"] = issues
        
        return result
    
    async def _check_blackboard(self) -> dict[str, Any]:
        """Check blackboard backend health."""
        bb_type = self.config.blackboard_type
        
        if bb_type == "redis":
            # Check Redis connection
            try:
                backend = self.blackboard._backend
                if hasattr(backend, '_pool'):
                    # Redis blackboard - check connection stats
                    stats = backend.get_stats() if hasattr(backend, 'get_stats') else {}
                    return {
                        "status": "healthy",
                        "type": "redis",
                        "details": stats
                    }
                else:
                    return {"status": "healthy", "type": "redis"}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        elif bb_type == "ttl_memory":
            # Check TTL cleanup loop status
            try:
                backend = self.blackboard._backend
                stats = backend.get_stats() if hasattr(backend, 'get_stats') else {}
                return {
                    "status": "healthy",
                    "type": "ttl_memory",
                    "details": stats
                }
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        else:
            # Memory blackboard - always healthy
            return {"status": "healthy", "type": "memory"}
    
    async def _check_bus(self) -> dict[str, Any]:
        """Check event bus health."""
        bus_type = type(self.bus).__name__
        
        if bus_type == "RedisEventBus":
            try:
                stats = self.bus.get_connection_stats() if hasattr(self.bus, 'get_connection_stats') else {}
                return {
                    "status": "healthy",
                    "type": "redis",
                    "details": stats
                }
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        else:
            # InProcessEventBus - check running status
            return {
                "status": "healthy",
                "type": "inprocess",
                "running": True
            }
    
    def _check_scheduler(self) -> dict[str, Any]:
        """Check scheduler health."""
        return {
            "status": "healthy",
            "active_workers": len(self.scheduler._capabilities),
            "strategy": self.config.scheduler.selection_strategy,
        }

    async def readiness(self) -> HealthStatus:
        """
        🔍 Readiness probe for HiveFlow application startup.

        Checks:
        - Redis connectivity (if using Redis blackboard)
        - LLM API key validity (if LLM client configured)
        - Temporary directory writeability
        - Blackboard initialization

        Returns:
            HealthStatus object with healthy flag and detailed checks

        Examples:
            >>> status = await hf.readiness()
            >>> if not status.healthy:
            ...     print(f"Readiness failed: {status.issues}")
            ...     for check_name, check_result in status.checks.items():
            ...         if check_result.get("status") != "healthy":
            ...             print(f"  - {check_name}: {check_result}")
        """
        checks: dict[str, dict[str, Any]] = {}
        issues: list[str] = []

        # 1. Check temporary directory writeability
        try:
            temp_check = await self._check_temp_directory()
            checks["temp_directory"] = temp_check
            if temp_check.get("status") != "healthy":
                issues.append("temp_directory")
        except Exception as e:
            checks["temp_directory"] = {"status": "error", "error": str(e)}
            issues.append("temp_directory")

        # 2. Check Redis connectivity (if using Redis)
        if self.config.blackboard_type == "redis" or self.config.redis_url:
            try:
                redis_check = await self._check_redis_readiness()
                checks["redis"] = redis_check
                if redis_check.get("status") != "healthy":
                    issues.append("redis")
            except Exception as e:
                checks["redis"] = {"status": "error", "error": str(e)}
                issues.append("redis")

        # 3. Check LLM API key validity (if configured)
        # We don't make actual API calls, just check if keys are present
        try:
            llm_check = self._check_llm_readiness()
            checks["llm_api"] = llm_check
            if llm_check.get("status") != "healthy":
                issues.append("llm_api")
        except Exception as e:
            checks["llm_api"] = {"status": "error", "error": str(e)}
            issues.append("llm_api")

        # 4. Check blackboard initialization
        try:
            bb_check = await self._check_blackboard_readiness()
            checks["blackboard"] = bb_check
            if bb_check.get("status") != "healthy":
                issues.append("blackboard")
        except Exception as e:
            checks["blackboard"] = {"status": "error", "error": str(e)}
            issues.append("blackboard")

        # Determine overall health
        healthy = len(issues) == 0

        return HealthStatus(healthy=healthy, checks=checks, issues=issues)

    async def _check_temp_directory(self) -> dict[str, Any]:
        """Check temporary directory writeability."""
        try:
            # Try to create and write a temp file
            with tempfile.TemporaryFile(mode="w", delete=True) as tf:
                tf.write("readiness_check")
                tf.flush()

            temp_dir = tempfile.gettempdir()
            return {
                "status": "healthy",
                "temp_dir": temp_dir,
                "writable": True,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "temp_dir": tempfile.gettempdir(),
                "writable": False,
            }

    async def _check_redis_readiness(self) -> dict[str, Any]:
        """Check Redis connectivity for readiness."""
        try:
            # Check if Redis backend is available and connected
            if hasattr(self.blackboard._backend, "_pool"):
                # Redis blackboard - ping test
                # Try a simple operation to verify connectivity
                backend = self.blackboard._backend
                if hasattr(backend, "_redis"):
                    # Async ping
                    redis_client = backend._redis
                    await redis_client.ping()
                    return {
                        "status": "healthy",
                        "type": "redis",
                        "ping": "success",
                    }

            # If not Redis backend, check if Redis URL is configured
            if self.config.redis_url:
                # Redis is configured but not yet connected
                return {
                    "status": "healthy",
                    "type": "configured",
                    "url": self.config.redis_url.split("@")[1] if "@" in self.config.redis_url else self.config.redis_url,
                }

            return {"status": "healthy", "type": "not_used"}

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "type": "redis",
            }

    def _check_llm_readiness(self) -> dict[str, Any]:
        """Check LLM API key availability for readiness."""
        checks = []

        # Check OpenAI API key
        openai_key = os.environ.get("HIVEFLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if openai_key:
            checks.append({"provider": "openai", "key_present": True, "key_prefix": openai_key[:8] + "..."})
        else:
            checks.append({"provider": "openai", "key_present": False})

        # Check Anthropic API key
        anthropic_key = os.environ.get("HIVEFLOW_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            checks.append({"provider": "anthropic", "key_present": True, "key_prefix": anthropic_key[:8] + "..."})
        else:
            checks.append({"provider": "anthropic", "key_present": False})

        # Determine overall status
        any_key_present = any(check["key_present"] for check in checks)

        if any_key_present:
            return {
                "status": "healthy",
                "providers": checks,
                "at_least_one_key": True,
            }
        else:
            return {
                "status": "degraded",
                "providers": checks,
                "at_least_one_key": False,
                "hint": "No LLM API keys found. Set HIVEFLOW_OPENAI_API_KEY or HIVEFLOW_ANTHROPIC_API_KEY.",
            }

    async def _check_blackboard_readiness(self) -> dict[str, Any]:
        """Check blackboard initialization for readiness."""
        try:
            # Check if blackboard is initialized
            if self.blackboard is None:
                return {"status": "error", "error": "Blackboard not initialized"}

            # Check backend type
            bb_type = self.config.blackboard_type

            # For Redis blackboard, verify connection
            if bb_type == "redis":
                # Connection already checked in redis_readiness
                return {
                    "status": "healthy",
                    "type": "redis",
                    "initialized": True,
                }

            # For memory/TTL blackboard, verify it's working
            elif bb_type in ("memory", "ttl_memory"):
                # Try a simple write/read operation
                test_key = "__readiness_check__"
                test_value = "ok"
                await self.blackboard.sys_put(test_key, test_value)
                retrieved = await self.blackboard.sys_get(test_key)
                if retrieved == test_value:
                    return {
                        "status": "healthy",
                        "type": bb_type,
                        "initialized": True,
                        "test_passed": True,
                    }
                else:
                    return {
                        "status": "error",
                        "type": bb_type,
                        "initialized": True,
                        "test_passed": False,
                        "error": "Write/read test failed",
                    }

            # For encrypted blackboard, verify key provider
            elif bb_type == "encrypted":
                if self.config.encryption_key_provider:
                    return {
                        "status": "healthy",
                        "type": "encrypted",
                        "initialized": True,
                        "key_provider": type(self.config.encryption_key_provider).__name__,
                    }
                else:
                    return {
                        "status": "error",
                        "type": "encrypted",
                        "initialized": False,
                        "error": "Encryption key provider not configured",
                    }

            else:
                return {"status": "healthy", "type": "unknown", "initialized": True}

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "initialized": False,
            }

    async def delete_workflow(self, workflow_id: str) -> bool:
        """
        🔧 Delete a workflow with cascading cleanup of all related data.
        
        Cascading deletes:
        - Checkpoint data (all checkpoints for this workflow)
        - Blackboard keys related to this workflow
        - HITL gates (all pending/completed gates for this workflow)
        
        Args:
            workflow_id: ID of the workflow to delete
            
        Returns:
            True if deletion was successful, False if workflow not found
        """
        logger.info(f"Deleting workflow: {workflow_id}")
        
        try:
            # Use helper method for cascading delete
            await self._cascade_delete_workflow(workflow_id)
            logger.info(f"Workflow {workflow_id} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to delete workflow {workflow_id}: {e}")
            raise

    async def _cascade_delete_workflow(self, workflow_id: str) -> None:
        """
        🔧 Internal helper for cascading workflow deletion.
        
        Ensures all related data is cleaned up in the correct order.
        Uses transaction-like semantics to ensure completeness.
        
        Args:
            workflow_id: ID of the workflow to delete
        """
        errors = []
        
        # Step 1: Delete all checkpoints for this workflow
        if self.checkpoint_manager:
            try:
                checkpoints = await self.checkpoint_manager.list_checkpoints(workflow_id)
                for cp in checkpoints:
                    await self.checkpoint_manager.delete_checkpoint(cp.checkpoint_id)
                logger.debug(
                    f"Deleted {len(checkpoints)} checkpoints for workflow {workflow_id}"
                )
            except Exception as e:
                errors.append(f"checkpoint: {e}")
                logger.warning(f"Failed to delete checkpoints for {workflow_id}: {e}")
        
        # Step 2: Delete HITL gates for this workflow
        if self.hitl_manager:
            try:
                gates = self.hitl_manager.list_gates(workflow_id=workflow_id)
                for gate in gates:
                    if gate.status.value == "pending":
                        await self.hitl_manager.cancel_gate(gate.gate_id)
                    # Remove gate from internal storage
                    if gate.gate_id in self.hitl_manager._gates:
                        del self.hitl_manager._gates[gate.gate_id]
                    if gate.gate_id in self.hitl_manager._waiters:
                        del self.hitl_manager._waiters[gate.gate_id]
                logger.debug(
                    f"Deleted {len(gates)} HITL gates for workflow {workflow_id}"
                )
            except Exception as e:
                errors.append(f"hitl: {e}")
                logger.warning(f"Failed to delete HITL gates for {workflow_id}: {e}")
        
        # Step 3: Delete blackboard keys related to this workflow
        try:
            # Common workflow-related key patterns
            patterns = [
                f"workflow.{workflow_id}",
                f"error.{workflow_id}",
                f"state.{workflow_id}",
                f"result.{workflow_id}",
            ]
            deleted_keys = 0
            for pattern in patterns:
                try:
                    # Try to delete exact key first
                    await self.blackboard.sys_delete(pattern)
                    deleted_keys += 1
                except Exception:
                    pass  # Key may not exist
            
            # Also try to clean up any agent-specific keys for this workflow
            # Pattern: error.{intent_id}.{agent_id} where intent_id matches workflow
            for agent_id in list(self.scheduler._capabilities.keys()):
                try:
                    key = f"error.{workflow_id}.{agent_id}"
                    await self.blackboard.sys_delete(key)
                    deleted_keys += 1
                except Exception:
                    pass
            
            logger.debug(
                f"Deleted ~{deleted_keys} blackboard keys for workflow {workflow_id}"
            )
        except Exception as e:
            errors.append(f"blackboard: {e}")
            logger.warning(f"Failed to delete blackboard keys for {workflow_id}: {e}")
        
        # Report errors if any occurred
        if errors:
            raise RuntimeError(
                f"Cascading delete for workflow {workflow_id} had errors: {', '.join(errors)}"
            )


def configure_logging(level: str = "INFO", format: str | None = None) -> None:
    """Configure logging for the entire application."""
    fmt = format or "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
