from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

MISSING = object()


@dataclass
class Expectation:
    state_key: str
    expected_schema: dict[str, Any]
    validation: str = ""
    deadline: float = 30.0
    use_json_schema: bool = False


@dataclass
class ECM:
    trace_id: str
    intent: str
    intent_id: str
    emitter: str
    expectation: Expectation | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    reply_to: str = ""
    timestamp: float = field(default_factory=time.monotonic)
    required_skills: list[str] = field(default_factory=list)
    priority: str = "normal"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Capability:
    agent_id: str
    skills: set[str]
    load: float = 0.0
    history: list[float] = field(default_factory=list)
    read_keys: set[str] = field(default_factory=set)
    write_keys: set[str] = field(default_factory=set)
    state: str = "starting"
    weight: float = 1.0
    pending_tasks: int = 0
    max_queue_size: int = 0

    def __post_init__(self):
        if not isinstance(self.skills, set):
            self.skills = set(self.skills)
        if not isinstance(self.read_keys, set):
            self.read_keys = set(self.read_keys)
        if not isinstance(self.write_keys, set):
            self.write_keys = set(self.write_keys)


class AbortExecutionException(Exception):
    """编排器节点明确要求中断整个流程"""

    pass


TaskGraph = dict[str, dict]

try:
    from .blackboard import (
        AuditedBlackboardView,
        BlackboardBackend,
        EncryptedBlackboard,
        EnvKeyProvider,
        FileKeyProvider,
        KeyProvider,
        MemoryBlackboard,
        OrchestratorReadonlyView,
        RedisBlackboard,
        SecureBlackboard,
        TTLMemoryBlackboard,
    )
    from .bus import EventBus, InProcessEventBus, RedisEventBus
    from .cell import Cell, Worker, ensure_error_writes
    from .checkpoint import (
        Checkpoint,
        CheckpointBackend,
        CheckpointManager,
        MemoryCheckpointBackend,
        SQLiteCheckpointBackend,
    )
    from .llm_client import (
        AnthropicClient,
        LLMClient,
        LLMMessage,
        LLMResponse,
        LLMToolDefinition,
        MockLLMClient,
        OpenAIClient,
    )
    from .cognitive_orchestrator import CognitiveOrchestrator, ExecutionResult, Plan, ResultCache
    from .evaluation import ABTester, BenchmarkSuite, EvaluationCriteria, EvaluationReport, Evaluator
    from .guards import InputGuard, InputGuardResult, OutputValidationResult, OutputValidator
    from .hitl import HITLAction, HITLGate, HITLManager, HITLStatus
    from .intent_parser import IntentParser, ParsedIntent
    from .logging_utils import TraceLogger, get_trace_logger
    from .mcp import (
        MCPClient,
        MCPPlugin,
        MCPPluginManager,
        MCPResource,
        MCPTool,
        MCPToolCallResult,
        MCPToolParam,
        MCPTransportType,
    )
    from .memory_manager import LongTermMemory, MemoryEntry, MemoryManager, ShortTermMemory
    from .metrics import MetricsCollector
    from .multimodal import (
        AudioProcessor,
        AudioTranscriptResult,
        ImageAnalysisResult,
        ImageGenerationResult,
        ImageProcessor,
        MediaContent,
        MediaType,
        MockAudioProcessor,
        MockImageProcessor,
        MockVideoProcessor,
        MultiModalPipeline,
        OpenAIAudioProcessor,
        OpenAIImageProcessor,
        OpenAIVideoProcessor,
        VideoProcessor,
        VideoSummaryResult,
    )
    from .orchestrator import DAGOrchestrator, DynamicOrchestrator
    from .app import HiveFlow, HiveFlowConfig, configure_logging
    from .plugin_marketplace import PluginCategory, PluginMarketplace, PluginSpec
    from .rag import (
        ChunkStrategy,
        Document,
        DocumentChunk,
        DocumentProcessor,
        DocumentType,
        DummyEmbeddingModel,
        EmbeddingModel,
        KnowledgeBase,
        KnowledgeBaseManager,
        MemoryVectorStore,
        RAGPipeline,
        RAGResult,
        SearchResult,
        TextChunker,
        VectorStore,
    )
    from .react_worker import ReActTool, ReActWorker, create_default_tools
    from .scheduler import (
        PRIORITY_ORDER,
        AuctionStrategy,
        GlobalLoadAwareStrategy,
        InProcessScheduler,
        LeastLoadedStrategy,
        Scheduler,
        SchedulerConfig,
        SelectionStrategy,
    )
    from .streaming import StreamBuffer, StreamEvent, StreamEventType, collect_stream
    from .validation import ValidationPipeline
except ImportError:
    from .blackboard import (
        AuditedBlackboardView,
        BlackboardBackend,
        EncryptedBlackboard,
        EnvKeyProvider,
        FileKeyProvider,
        KeyProvider,
        MemoryBlackboard,
        OrchestratorReadonlyView,
        RedisBlackboard,
        SecureBlackboard,
        TTLMemoryBlackboard,
    )
    from .bus import EventBus, InProcessEventBus, RedisEventBus
    from .cell import Cell, Worker, ensure_error_writes
    from .checkpoint import (
        Checkpoint,
        CheckpointBackend,
        CheckpointManager,
        MemoryCheckpointBackend,
        SQLiteCheckpointBackend,
    )
    from .llm_client import (
        AnthropicClient,
        LLMClient,
        LLMMessage,
        LLMResponse,
        LLMToolDefinition,
        MockLLMClient,
        OpenAIClient,
    )
    from .cognitive_orchestrator import CognitiveOrchestrator, ExecutionResult, Plan, ResultCache
    from .evaluation import ABTester, BenchmarkSuite, EvaluationCriteria, EvaluationReport, Evaluator
    from .guards import InputGuard, InputGuardResult, OutputValidationResult, OutputValidator
    from .hitl import HITLAction, HITLGate, HITLManager, HITLStatus
    from .intent_parser import IntentParser, ParsedIntent
    from .logging_utils import TraceLogger, get_trace_logger
    from .mcp import (
        MCPClient,
        MCPPlugin,
        MCPPluginManager,
        MCPResource,
        MCPTool,
        MCPToolCallResult,
        MCPToolParam,
        MCPTransportType,
    )
    from .memory_manager import LongTermMemory, MemoryEntry, MemoryManager, ShortTermMemory
    from .metrics import MetricsCollector
    from .multimodal import (
        AudioProcessor,
        AudioTranscriptResult,
        ImageAnalysisResult,
        ImageGenerationResult,
        ImageProcessor,
        MediaContent,
        MediaType,
        MockAudioProcessor,
        MockImageProcessor,
        MockVideoProcessor,
        MultiModalPipeline,
        OpenAIAudioProcessor,
        OpenAIImageProcessor,
        OpenAIVideoProcessor,
        VideoProcessor,
        VideoSummaryResult,
    )
    from .orchestrator import DAGOrchestrator, DynamicOrchestrator
    from .app import HiveFlow, HiveFlowConfig, configure_logging
    from .plugin_marketplace import PluginCategory, PluginMarketplace, PluginSpec
    from .rag import (
        ChunkStrategy,
        Document,
        DocumentChunk,
        DocumentProcessor,
        DocumentType,
        DummyEmbeddingModel,
        EmbeddingModel,
        KnowledgeBase,
        KnowledgeBaseManager,
        MemoryVectorStore,
        RAGPipeline,
        RAGResult,
        SearchResult,
        TextChunker,
        VectorStore,
    )
    from .react_worker import ReActTool, ReActWorker, create_default_tools
    from .scheduler import (
        PRIORITY_ORDER,
        AuctionStrategy,
        GlobalLoadAwareStrategy,
        InProcessScheduler,
        LeastLoadedStrategy,
        Scheduler,
        SchedulerConfig,
        SelectionStrategy,
    )
    from .streaming import StreamBuffer, StreamEvent, StreamEventType, collect_stream
    from .validation import ValidationPipeline

try:
    from .observability import (
        HiveFlowLogger,
        PrometheusMetricsExporter,
        create_prometheus_registry,
        create_span,
        setup_structured_logging,
        setup_tracing,
        trace_workflow_execution,
    )
except ImportError:
    pass

__all__ = [
    "ECM",
    "MISSING",
    "PRIORITY_ORDER",
    "ABTester",
    "AbortExecutionException",
    "AnthropicClient",
    "AuctionStrategy",
    "AudioProcessor",
    "AudioTranscriptResult",
    "AuditedBlackboardView",
    "BenchmarkSuite",
    "BlackboardBackend",
    "Capability",
    "Cell",
    "Checkpoint",
    "CheckpointBackend",
    "CheckpointManager",
    "ChunkStrategy",
    "CognitiveOrchestrator",
    "DAGOrchestrator",
    "Document",
    "DocumentChunk",
    "DocumentProcessor",
    "DocumentType",
    "DummyEmbeddingModel",
    "DynamicOrchestrator",
    "EmbeddingModel",
    "EncryptedBlackboard",
    "EnvKeyProvider",
    "EvaluationCriteria",
    "EvaluationReport",
    "Evaluator",
    "EventBus",
    "ExecutionResult",
    "Expectation",
    "FileKeyProvider",
    "GlobalLoadAwareStrategy",
    "HITLAction",
    "HITLGate",
    "HITLManager",
    "HITLStatus",
    "HiveFlow",
    "HiveFlowConfig",
    "HiveFlowLogger",
    "ImageAnalysisResult",
    "ImageGenerationResult",
    "ImageProcessor",
    "InProcessEventBus",
    "InProcessScheduler",
    "InputGuard",
    "InputGuardResult",
    "IntentParser",
    "KeyProvider",
    "KnowledgeBase",
    "KnowledgeBaseManager",
    "LLMClient",
    "LLMMessage",
    "LLMResponse",
    "LLMToolDefinition",
    "LeastLoadedStrategy",
    "LongTermMemory",
    "MCPClient",
    "MCPPlugin",
    "MCPPluginManager",
    "MCPResource",
    "MCPTool",
    "MCPToolCallResult",
    "MCPToolParam",
    "MCPTransportType",
    "MediaContent",
    "MediaType",
    "MemoryBlackboard",
    "MemoryCheckpointBackend",
    "MemoryEntry",
    "MemoryManager",
    "MemoryVectorStore",
    "MetricsCollector",
    "MockAudioProcessor",
    "MockImageProcessor",
    "MockLLMClient",
    "MockVideoProcessor",
    "MultiModalPipeline",
    "OpenAIAudioProcessor",
    "OpenAIClient",
    "OpenAIImageProcessor",
    "OpenAIVideoProcessor",
    "OrchestratorReadonlyView",
    "OutputValidationResult",
    "OutputValidator",
    "ParsedIntent",
    "Plan",
    "PluginCategory",
    "PluginMarketplace",
    "PluginSpec",
    # Observability (optional subpackage)
    "PrometheusMetricsExporter",
    "RAGPipeline",
    "RAGResult",
    "ReActTool",
    "ReActWorker",
    "RedisBlackboard",
    "RedisEventBus",
    "ResultCache",
    "SQLiteCheckpointBackend",
    "Scheduler",
    "SchedulerConfig",
    "SearchResult",
    "SecureBlackboard",
    "SelectionStrategy",
    "ShortTermMemory",
    "StreamBuffer",
    "StreamEvent",
    "StreamEventType",
    "TTLMemoryBlackboard",
    "TaskGraph",
    "TextChunker",
    "TraceLogger",
    "ValidationPipeline",
    "VectorStore",
    "VideoProcessor",
    "VideoSummaryResult",
    "Worker",
    "collect_stream",
    "configure_logging",
    "create_default_tools",
    "create_prometheus_registry",
    "create_span",
    "ensure_error_writes",
    "get_trace_logger",
    "setup_structured_logging",
    "setup_tracing",
    "trace_workflow_execution",
]
