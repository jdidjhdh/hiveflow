from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ECM:
    trace_id: str = ""
    intent: str = ""
    intent_id: str = ""
    emitter: str = ""
    expectation: Optional[Any] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    reply_to: str = ""
    timestamp: float = 0.0
    required_skills: list = field(default_factory=list)
    priority: str = "normal"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CognitiveECM(ECM):
    user_query: str = ""
    conversation_id: str = ""
    plan_snapshot: Optional[Dict] = None
    context: Dict[str, Any] = field(default_factory=dict)
