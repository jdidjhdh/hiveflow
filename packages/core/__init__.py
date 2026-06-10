from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable, Tuple
import time

MISSING = object()


@dataclass
class Expectation:
    state_key: str
    expected_schema: Dict[str, Any]
    validation: str = ""
    deadline: float = 30.0
    use_json_schema: bool = False


@dataclass
class ECM:
    trace_id: str
    intent: str
    intent_id: str
    emitter: str
    expectation: Optional[Expectation] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    reply_to: str = ""
    timestamp: float = field(default_factory=time.monotonic)
    required_skills: List[str] = field(default_factory=list)
    priority: str = "normal"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Capability:
    agent_id: str
    skills: Set[str]
    load: float = 0.0
    history: List[float] = field(default_factory=list)
    read_keys: Set[str] = field(default_factory=set)
    write_keys: Set[str] = field(default_factory=set)
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


TaskGraph = Dict[str, dict]

try:
    from .bus import EventBus, InProcessEventBus, RedisEventBus
    from .scheduler import (Scheduler, SchedulerConfig, InProcessScheduler, SelectionStrategy,
                             LeastLoadedStrategy, AuctionStrategy, GlobalLoadAwareStrategy, PRIORITY_ORDER)
    from .blackboard import (BlackboardBackend, MemoryBlackboard, TTLMemoryBlackboard, RedisBlackboard,
                              SecureBlackboard, AuditedBlackboardView, OrchestratorReadonlyView,
                              EncryptedBlackboard, KeyProvider, EnvKeyProvider, FileKeyProvider)
    from .validation import ValidationPipeline
    from .cell import Worker, Cell
    from .orchestrator import DAGOrchestrator, DynamicOrchestrator
    from .metrics import MetricsCollector
    from .logging_utils import TraceLogger, get_trace_logger
    from .app import HiveFlowConfig, HiveFlow
    # New modules are in the hiveflow/ subdirectory package
    from .hiveflow.llm_client import (
        LLMClient, LLMMessage, LLMToolDefinition, LLMResponse,
        OpenAIClient, MockLLMClient, AnthropicClient,
    )
    from .hiveflow.intent_parser import IntentParser, ParsedIntent
    from .hiveflow.memory_manager import MemoryManager, ShortTermMemory, LongTermMemory, MemoryEntry
    from .hiveflow.react_worker import ReActWorker, ReActTool, create_default_tools
    from .hiveflow.cognitive_orchestrator import CognitiveOrchestrator, Plan, ExecutionResult, ResultCache
    from .hiveflow.guards import InputGuard, OutputValidator, InputGuardResult, OutputValidationResult
    from .hiveflow.checkpoint import (
        CheckpointManager, Checkpoint, CheckpointBackend,
        MemoryCheckpointBackend,
    )
    from .hiveflow.streaming import StreamBuffer, StreamEvent, StreamEventType, collect_stream
    from .hiveflow.hitl import HITLManager, HITLGate, HITLStatus, HITLAction
    from .hiveflow.evaluation import Evaluator, EvaluationReport, BenchmarkSuite, ABTester, EvaluationCriteria
    from .hiveflow.rag import (
        DocumentProcessor, Document, DocumentType,
        TextChunker, DocumentChunk, ChunkStrategy,
        VectorStore, MemoryVectorStore, SearchResult,
        RAGPipeline, RAGResult, EmbeddingModel, DummyEmbeddingModel,
        KnowledgeBaseManager, KnowledgeBase,
    )
    from .hiveflow.mcp import (
        MCPClient, MCPTool, MCPToolParam, MCPResource, MCPToolCallResult, MCPTransportType,
        MCPPluginManager, MCPPlugin,
    )
    from .hiveflow.plugin_marketplace import PluginMarketplace, PluginSpec, PluginCategory
    from .hiveflow.multimodal import (
        MultiModalPipeline, ImageProcessor, AudioProcessor, VideoProcessor,
        OpenAIImageProcessor, MockImageProcessor,
        OpenAIAudioProcessor, MockAudioProcessor,
        OpenAIVideoProcessor, MockVideoProcessor,
        MediaContent, MediaType,
        ImageAnalysisResult, AudioTranscriptResult, VideoSummaryResult, ImageGenerationResult,
    )
except ImportError:
    from bus import EventBus, InProcessEventBus, RedisEventBus
    from scheduler import (Scheduler, SchedulerConfig, InProcessScheduler, SelectionStrategy,
                             LeastLoadedStrategy, AuctionStrategy, GlobalLoadAwareStrategy, PRIORITY_ORDER)
    from blackboard import (BlackboardBackend, MemoryBlackboard, TTLMemoryBlackboard, RedisBlackboard,
                              SecureBlackboard, AuditedBlackboardView, OrchestratorReadonlyView,
                              EncryptedBlackboard, KeyProvider, EnvKeyProvider, FileKeyProvider)
    from validation import ValidationPipeline
    from cell import Worker, Cell
    from orchestrator import DAGOrchestrator, DynamicOrchestrator
    from metrics import MetricsCollector
    from logging_utils import TraceLogger, get_trace_logger
    from app import HiveFlowConfig, HiveFlow

__all__ = [
    "MISSING",
    "Expectation",
    "ECM",
    "Capability",
    "AbortExecutionException",
    "TaskGraph",
    "EventBus",
    "InProcessEventBus",
    "RedisEventBus",
    "Scheduler",
    "SchedulerConfig",
    "InProcessScheduler",
    "SelectionStrategy",
    "LeastLoadedStrategy",
    "AuctionStrategy",
    "GlobalLoadAwareStrategy",
    "PRIORITY_ORDER",
    "BlackboardBackend",
    "MemoryBlackboard",
    "TTLMemoryBlackboard",
    "RedisBlackboard",
    "SecureBlackboard",
    "AuditedBlackboardView",
    "OrchestratorReadonlyView",
    "EncryptedBlackboard",
    "KeyProvider",
    "EnvKeyProvider",
    "FileKeyProvider",
    "ValidationPipeline",
    "Worker",
    "Cell",
    "DAGOrchestrator",
    "DynamicOrchestrator",
    "MetricsCollector",
    "TraceLogger",
    "get_trace_logger",
    "HiveFlowConfig",
    "HiveFlow",
    "LLMClient",
    "LLMMessage",
    "LLMToolDefinition",
    "LLMResponse",
    "OpenAIClient",
    "MockLLMClient",
    "AnthropicClient",
    "IntentParser",
    "ParsedIntent",
    "MemoryManager",
    "ShortTermMemory",
    "LongTermMemory",
    "MemoryEntry",
    "ReActWorker",
    "ReActTool",
    "create_default_tools",
    "CognitiveOrchestrator",
    "Plan",
    "ExecutionResult",
    "ResultCache",
    "InputGuard",
    "OutputValidator",
    "InputGuardResult",
    "OutputValidationResult",
    "CheckpointManager",
    "Checkpoint",
    "CheckpointBackend",
    "MemoryCheckpointBackend",
    "StreamBuffer",
    "StreamEvent",
    "StreamEventType",
    "collect_stream",
    "HITLManager",
    "HITLGate",
    "HITLStatus",
    "HITLAction",
    "Evaluator",
    "EvaluationReport",
    "BenchmarkSuite",
    "ABTester",
    "EvaluationCriteria",
    "DocumentProcessor",
    "Document",
    "DocumentType",
    "TextChunker",
    "DocumentChunk",
    "ChunkStrategy",
    "VectorStore",
    "MemoryVectorStore",
    "SearchResult",
    "RAGPipeline",
    "RAGResult",
    "EmbeddingModel",
    "DummyEmbeddingModel",
    "KnowledgeBaseManager",
    "KnowledgeBase",
    "MCPClient",
    "MCPTool",
    "MCPToolParam",
    "MCPResource",
    "MCPToolCallResult",
    "MCPTransportType",
    "MCPPluginManager",
    "MCPPlugin",
    "PluginMarketplace",
    "PluginSpec",
    "PluginCategory",
    "MultiModalPipeline",
    "ImageProcessor",
    "AudioProcessor",
    "VideoProcessor",
    "OpenAIImageProcessor",
    "MockImageProcessor",
    "OpenAIAudioProcessor",
    "MockAudioProcessor",
    "OpenAIVideoProcessor",
    "MockVideoProcessor",
    "MediaContent",
    "MediaType",
    "ImageAnalysisResult",
    "AudioTranscriptResult",
    "VideoSummaryResult",
    "ImageGenerationResult",
]