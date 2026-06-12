"""Echo / mock LLM for Studio Agent mode without external API keys."""
from __future__ import annotations

import hashlib
import json
import re

from llm.base import LLMClient


class EchoLLM(LLMClient):
    async def complete(self, messages, **kwargs):
        return '{"intent":"general","required_skills":["general"],"payload":{},"priority":"normal"}'

    def _last_user_message(self, messages) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return str(msg.get("content") or "")
        return ""

    def _extract_planning_query(self, messages) -> str:
        last_user = self._last_user_message(messages)
        lower = last_user.lower()
        if "user request:" in lower:
            return last_user.split(":", 1)[-1].strip()
        if "for this user request:" in lower:
            return last_user.split("for this user request:", 1)[-1].strip()
        for msg in messages:
            content = str(msg.get("content") or "")
            if "Conversation:" not in content:
                continue
            try:
                conv_raw = content.split("Conversation:", 1)[1].split("Long-term:", 1)[0].strip()
                conv = json.loads(conv_raw)
                for item in reversed(conv):
                    if item.get("role") == "user" and item.get("content"):
                        return str(item["content"])
            except (json.JSONDecodeError, TypeError, IndexError):
                pass
        return last_user.strip() or "general task"

    def _slug(self, text: str, max_len: int = 16) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        if slug:
            return slug[:max_len]
        digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
        return f"task_{digest}"

    def _build_echo_intent(self, user_input: str) -> dict:
        q = user_input.lower()
        if any(k in q for k in ("search", "搜索", "检索", "research", "find")):
            return {"intent": "research", "required_skills": ["general", "summarize"], "payload": {"query": user_input}, "priority": "normal"}
        if any(k in q for k in ("code", "代码", "python", "debug", "编程")):
            return {"intent": "code_task", "required_skills": ["general", "summarize"], "payload": {"query": user_input}, "priority": "normal"}
        if any(k in q for k in ("report", "报告", "analyze", "分析", "趋势")):
            return {"intent": "analysis_report", "required_skills": ["general", "summarize"], "payload": {"query": user_input}, "priority": "normal"}
        return {"intent": "general", "required_skills": ["general"], "payload": {"query": user_input}, "priority": "normal"}

    def _build_echo_plan(self, query: str) -> dict:
        q = query.lower()
        if any(k in q for k in ("搜索", "search", "检索", "research", "查询资料", "find")):
            return {
                "search_data": {"task": "general", "depends_on": []},
                "analyze_results": {"task": "summarize", "depends_on": ["search_data"]},
                "final_answer": {"task": "summarize", "depends_on": ["analyze_results"]},
            }
        if any(k in q for k in ("代码", "code", "编程", "python", "debug", "implement")):
            return {
                "write_code": {"task": "general", "depends_on": []},
                "review_code": {"task": "summarize", "depends_on": ["write_code"]},
                "final_answer": {"task": "summarize", "depends_on": ["review_code"]},
            }
        if any(k in q for k in ("报告", "report", "分析", "analyze", "趋势", "trend")):
            return {
                "fetch_data": {"task": "general", "depends_on": []},
                "analyze_trend": {"task": "general", "depends_on": ["fetch_data"]},
                "generate_report": {"task": "summarize", "depends_on": ["analyze_trend"]},
                "final_answer": {"task": "summarize", "depends_on": ["generate_report"]},
            }
        if any(k in q for k in ("并行", "parallel", "同时", "multiple")):
            return {
                "branch_a": {"task": "general", "depends_on": []},
                "branch_b": {"task": "general", "depends_on": []},
                "merge_results": {"task": "summarize", "depends_on": ["branch_a", "branch_b"]},
                "final_answer": {"task": "summarize", "depends_on": ["merge_results"]},
            }
        tokens = [t for t in re.split(r"[\s,，、；;]+", query.strip()) if t][:4]
        if len(tokens) >= 3:
            nodes: dict = {}
            prev = None
            for i, token in enumerate(tokens[:3]):
                name = f"step_{i + 1}_{self._slug(token)}"
                nodes[name] = {"task": "general", "depends_on": [prev] if prev else []}
                prev = name
            nodes["final_answer"] = {"task": "summarize", "depends_on": [prev]}
            return nodes
        slug = self._slug(query[:32] or "task")
        step_name = f"handle_{slug}"
        return {
            step_name: {"task": "general", "depends_on": []},
            "final_answer": {"task": "summarize", "depends_on": [step_name]},
        }

    async def complete_json(self, messages, **kwargs):
        last_user = self._last_user_message(messages)
        lower = last_user.lower()
        is_planning = (
            "taskgraph" in lower
            or "generate taskgraph" in lower
            or "generate graph" in lower
            or "user request:" in lower
        )
        if is_planning:
            query = self._extract_planning_query(messages)
            return self._build_echo_plan(query)
        return self._build_echo_intent(last_user)

    async def stream(self, messages, **kwargs):
        yield "ok"

    async def embed(self, texts):
        return [[0.0] * 8 for _ in texts]


def create_echo_llm() -> EchoLLM:
    return EchoLLM()
