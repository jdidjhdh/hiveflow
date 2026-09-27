from dataclasses import dataclass, field
from typing import Any


@dataclass
class ECM:
    trace_id: str = ""
    intent: str = ""
    intent_id: str = ""
    emitter: str = ""
    expectation: Any | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    reply_to: str = ""
    timestamp: float = 0.0
    required_skills: list = field(default_factory=list)
    priority: str = "normal"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CognitiveECM(ECM):
    user_query: str = ""
    conversation_id: str = ""
    plan_snapshot: dict | None = None
    context: dict[str, Any] = field(default_factory=dict)
