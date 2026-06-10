import uuid
import json
from typing import Dict
try:
    from .llm.base import LLMClient
except ImportError:
    from llm.base import LLMClient
try:
    from .protocol import CognitiveECM
except ImportError:
    from protocol import CognitiveECM


class IntentParser:
    def __init__(self, llm: LLMClient, skill_registry: Dict[str, str]):
        self.llm = llm
        self.skill_registry = skill_registry

    async def parse(self, user_input, conversation_id="", context=None) -> CognitiveECM:
        skills_desc = "\n".join([f"- {n}: {d}" for n, d in self.skill_registry.items()])
        messages = [
            {"role": "system", "content": f"""You are an intent parser. Output JSON:
- intent: short intent name
- required_skills: list of skills (from available)
- payload: parameters
- priority: critical/high/normal/low/background
Available skills:
{skills_desc}
Context: {json.dumps(context or {}, ensure_ascii=False)}"""},
            {"role": "user", "content": user_input}
        ]
        data = await self.llm.complete_json(messages)
        return CognitiveECM(
            trace_id=str(uuid.uuid4()),
            intent=data.get("intent", "user_request"),
            intent_id=str(uuid.uuid4()),
            emitter="intent_parser",
            required_skills=data.get("required_skills", []),
            payload=data.get("payload", {}),
            priority=data.get("priority", "normal"),
            user_query=user_input,
            conversation_id=conversation_id
        )
