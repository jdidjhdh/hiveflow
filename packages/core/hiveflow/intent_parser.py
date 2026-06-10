"""HiveFlow - IntentParser

LLM-driven intent parser that converts natural language user requests
into structured TaskGraph definitions that the orchestrator can execute.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from . import LLMClient, LLMMessage, TaskGraph, LLMToolDefinition
except ImportError:
    from hiveflow import LLMClient, LLMMessage, TaskGraph, LLMToolDefinition

logger = logging.getLogger(__name__)


@dataclass
class ParsedIntent:
    """Result of intent parsing."""
    intent_type: str  # "single_task", "pipeline", "conditional", "loop", "unknown"
    description: str
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    raw_response: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


INTENT_SYSTEM_PROMPT = """You are an intent parser for a multi-agent workflow orchestration system called HiveFlow.

Your task is to analyze the user's natural language request and convert it into a structured workflow definition.

Available node types:
- "task": A single agent task with a skill (e.g., "research", "write", "review", "analyze")
- "condition": A conditional branch that evaluates a condition and routes to different paths
- "loop": A loop that repeats a sub-workflow
- "subgraph": A nested workflow group
- "dynamic": A dynamic node that can generate sub-nodes at runtime

Output MUST be valid JSON with this schema:
{
  "intent_type": "single_task|pipeline|conditional|loop|unknown",
  "description": "brief description of the workflow",
  "nodes": [
    {
      "id": "node_id",
      "type": "task|condition|loop|subgraph|dynamic",
      "skill": "skill_name (for task nodes)",
      "label": "display label",
      "config": {"key": "value"}
    }
  ],
  "edges": [
    {"source": "node_id", "target": "node_id", "label": "edge_label (optional)"}
  ],
  "confidence": 0.0_to_1.0
}

Rules:
1. Node IDs must be unique and use lowercase_snake_case
2. Edges must reference existing node IDs
3. For pipelines, connect nodes sequentially
4. For conditional workflows, use "condition" type with "yes"/"no" edge labels
5. For loops, use "loop" type with edges cycling back
6. If the intent is unclear, set intent_type to "unknown" and confidence < 0.5
7. ALWAYS return ONLY valid JSON, no markdown, no explanation
"""


class IntentParser:
    """Parses natural language intents into structured TaskGraph definitions."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "",
        system_prompt: str = "",
        available_skills: Optional[List[str]] = None,
    ):
        self.llm_client = llm_client
        self.model = model
        self.system_prompt = system_prompt or INTENT_SYSTEM_PROMPT
        self.available_skills = available_skills or [
            "research", "write", "review", "analyze", "summarize",
            "classify", "extract", "translate", "validate", "generate",
        ]

        if self.available_skills:
            self.system_prompt += f"\n\nAvailable skills: {', '.join(self.available_skills)}"

    async def parse(self, user_input: str) -> ParsedIntent:
        """Parse a user's natural language input into a structured workflow."""
        messages = [
            LLMMessage(role="system", content=self.system_prompt),
            LLMMessage(role="user", content=f"Parse this workflow request:\n\n{user_input}"),
        ]

        try:
            response = await self.llm_client.chat(
                messages=messages,
                model=self.model,
                temperature=0.1,
                max_tokens=2048,
            )

            # Extract JSON from response (strip markdown code blocks if present)
            content = response.content.strip()
            if content.startswith("```"):
                # Remove markdown code block
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

            parsed = json.loads(content)

            return ParsedIntent(
                intent_type=parsed.get("intent_type", "unknown"),
                description=parsed.get("description", ""),
                nodes=parsed.get("nodes", []),
                edges=parsed.get("edges", []),
                confidence=parsed.get("confidence", 0.0),
                raw_response=response.content,
                metadata={
                    "model": response.model,
                    "latency_ms": response.latency_ms,
                    "usage": response.usage,
                },
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Intent parsing failed: {e}")
            return ParsedIntent(
                intent_type="unknown",
                description=f"Failed to parse: {str(e)}",
                confidence=0.0,
                raw_response="",
            )
        except Exception as e:
            logger.error(f"Intent parsing error: {e}")
            return ParsedIntent(
                intent_type="unknown",
                description=f"Error: {str(e)}",
                confidence=0.0,
                raw_response="",
            )

    def to_task_graph(self, parsed: ParsedIntent) -> Optional[TaskGraph]:
        """Convert a ParsedIntent into a TaskGraph for execution."""
        if parsed.intent_type == "unknown" or not parsed.nodes:
            return None

        graph: TaskGraph = {}

        # Build task functions for each node
        for node in parsed.nodes:
            node_id = node["id"]
            node_type = node.get("type", "task")
            skill = node.get("skill", "")
            label = node.get("label", node_id)
            config = node.get("config", {})

            # Create a placeholder task function
            async def placeholder_task(deps, blackboard, _skill=skill, _label=label, _config=config):
                await blackboard.put(f"result.{_label}", {"skill": _skill, "config": _config, "deps": deps})
                return {"status": "completed", "skill": _skill, "label": _label}

            graph[node_id] = {
                "task": placeholder_task,
                "depends_on": [],  # Will be filled from edges
                "skill": skill,
                "label": label,
            }

        # Fill depends_on from edges
        for edge in parsed.edges:
            target = edge["target"]
            source = edge["source"]
            if target in graph and source in graph:
                graph[target]["depends_on"].append(source)

        return graph
