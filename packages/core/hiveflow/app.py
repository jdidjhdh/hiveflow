import importlib.util
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

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

_FERNET_AVAILABLE = importlib.util.find_spec("cryptography.fernet") is not None
_JSONSCHEMA_AVAILABLE = importlib.util.find_spec("jsonschema") is not None
_REDIS_AVAILABLE = importlib.util.find_spec("redis") is not None


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
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    blackboard_type: str = "memory"  # memory, ttl_memory, redis, encrypted
    encryption_key_provider: KeyProvider | None = None
    redis_url: str | None = None
    redis_db: int = 0
    redis_max_connections: int = 10
    redis_socket_timeout: float = 5.0
    redis_blackboard_poll_interval: float = 0.05
    blackboard_prefix: str = "hiveflow"
    max_audit_entries: int = 1000
    use_json_schema: bool = False
    default_ttl: float | None = None
    worker_max_queue_size: int = 100
    encrypt_compression: bool = False
    log_level: str = "INFO"
    enable_hitl: bool = False
    enable_checkpoint: bool = False
    enable_rag: bool = False
    checkpoint_backend: str = "memory"  # memory | sqlite
    checkpoint_db_path: str = "hiveflow_checkpoints.db"

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
        if self.worker_max_queue_size < 1:
            raise ValueError("worker_max_queue_size must be >= 1")
        if self.redis_url is not None and not self.redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("redis_url must start with redis:// or rediss://")
        if self.checkpoint_backend not in ("memory", "sqlite"):
            raise ValueError("checkpoint_backend must be 'memory' or 'sqlite'")

    @classmethod
    def from_env(cls, prefix: str = "HIVEFLOW") -> "HiveFlowConfig":
        """Create HiveFlowConfig from environment variables.

        Environment variables (with HIVEFLOW_ prefix):
            BLACKBOARD_TYPE: memory, ttl_memory, redis, encrypted (default: memory)
            REDIS_URL: Redis connection URL (default: redis://localhost)
            REDIS_DB: Redis database number (default: 0)
            REDIS_MAX_CONNECTIONS: Max connection pool size (default: 10)
            REDIS_SOCKET_TIMEOUT: Socket timeout in seconds (default: 5.0)
            REDIS_POLL_INTERVAL: Blackboard poll interval in seconds (default: 0.05)
            PREFIX: Key prefix (default: hiveflow)
            MAX_AUDIT_ENTRIES: Max audit log entries (default: 1000)
            DEFAULT_TTL: Default TTL in seconds (default: None)
            WORKER_MAX_QUEUE_SIZE: Max worker queue size (default: 100)
            ENCRYPT_COMPRESSION: Enable compression for encrypted blackboard (default: false)
            LOG_LEVEL: Logging level (default: INFO)
            ENCRYPTION_KEY_SOURCE: env or file (default: env)
            ENCRYPTION_KEY_ENV_VAR: Env var name for key (default: HIVEFLOW_ENCRYPTION_KEY)
            ENCRYPTION_KEY_FILE: Path to key file
            USE_JSON_SCHEMA: Enable JSON schema validation (default: false)
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
        bb_type = _env("BLACKBOARD_TYPE", "memory")
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
        default_ttl = float(default_ttl_str) if default_ttl_str else None

        config = cls(
            blackboard_type=bb_type,
            encryption_key_provider=encryption_key_provider,
            redis_url=_env("REDIS_URL", None),
            redis_db=_env_int("REDIS_DB", 0),
            redis_max_connections=_env_int("REDIS_MAX_CONNECTIONS", 10),
            redis_socket_timeout=_env_float("REDIS_SOCKET_TIMEOUT", 5.0),
            redis_blackboard_poll_interval=_env_float("REDIS_POLL_INTERVAL", 0.05),
            blackboard_prefix=_env("PREFIX", "hiveflow"),
            max_audit_entries=_env_int("MAX_AUDIT_ENTRIES", 1000),
            use_json_schema=_env_bool("USE_JSON_SCHEMA", False),
            default_ttl=default_ttl,
            worker_max_queue_size=_env_int("WORKER_MAX_QUEUE_SIZE", 100),
            encrypt_compression=_env_bool("ENCRYPT_COMPRESSION", False),
            log_level=_env("LOG_LEVEL", "INFO"),
        )
        config.validate()
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

        self.blackboard = SecureBlackboard(base_bb, max_audit=self.config.max_audit_entries)

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
                        "Install with: pip install hiveflow[checkpoint]"
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


def configure_logging(level: str = "INFO", format: str | None = None) -> None:
    """Configure logging for the entire application."""
    fmt = format or "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
