# -*- coding: utf-8 -*-
"""FCToolSkill 单元测试：schema 构建、原生 FC 执行、参数错误重试、文本降级。"""
import asyncio
import json

import pytest

from worker.fc_skill import FCToolSkill


class StubLLM:
    """可控 stub：按消息内容返回工具调用或文本。"""

    def __init__(self):
        self.calls = []

    async def complete_with_tools(self, messages, tools, tool_choice="auto", **kwargs):
        self.calls.append(("fc", messages, tools))
        # 解析最后一条 user 消息，模拟模型决定
        last = messages[-1]["content"]
        if "触发参数错误" in last:
            return [{"name": "calculator", "arguments": {"expr2": "1"}}], None
        if "工具失败重试" in last:
            return [{"name": "calculator", "arguments": {"expr": "1/0"}}], None
        return [{"name": "calculator", "arguments": {"expr": "1+1"}}], None

    async def complete(self, messages, **kwargs):
        self.calls.append(("text", messages))
        # 后处理回合：把工具结果里的答案提取出来
        return "2"


def tool_calc(expr):
    if expr == "1/0":
        raise ZeroDivisionError("div by zero")
    return eval(expr)  # noqa: S307 测试用


def make_skill(llm):
    return FCToolSkill(
        llm=llm,
        name="calculator",
        description="计算数学表达式",
        parameters={
            "type": "object",
            "properties": {"expr": {"type": "string"}},
            "required": ["expr"],
        },
        executor=tool_calc,
        max_retries=2,
    )


def test_schema_structure():
    skill = make_skill(StubLLM())
    assert skill.schema["type"] == "function"
    assert skill.schema["function"]["name"] == "calculator"
    assert skill.schema["function"]["parameters"]["required"] == ["expr"]


@pytest.mark.asyncio
async def test_fc_success_with_postprocess():
    llm = StubLLM()
    skill = make_skill(llm)
    out = await skill.run("计算 1+1")
    assert out["provider"] == "fc"
    assert out["answer"] == "2"
    assert out["result"] == 2
    # 有 FC 调用 + 后处理文本回合
    kinds = [c[0] for c in llm.calls]
    assert "fc" in kinds and "text" in kinds


@pytest.mark.asyncio
async def test_type_error_retry():
    llm = StubLLM()
    skill = make_skill(llm)
    out = await skill.run("触发参数错误 1+1")
    # 参数错误重试后最终成功（第二次 FC 返回正确参数）
    assert out["provider"] == "fc"
    assert out["answer"] == "2"


@pytest.mark.asyncio
async def test_text_fallback_when_unsupported():
    class NoFC:
        async def complete_with_tools(self, *a, **k):
            raise NotImplementedError("no fc")

        async def complete(self, messages, **kwargs):
            return '{"expr": "3*4"}'

    skill = FCToolSkill(
        llm=NoFC(), name="calculator", description="d",
        parameters={"type": "object", "properties": {"expr": {"type": "string"}}, "required": ["expr"]},
        executor=tool_calc,
    )
    out = await skill.run("计算 3*4")
    assert out["provider"] == "text"
    assert out["result"] == 12
