"""
FCToolSkill：HiveFlow 原生 function calling 技能协议。

背景（基准实测结论）：
- 旧路径：Skill handler 内用 LLM 生成文本 JSON → 正则抠取 → json.loads，
  存在偶发解析失败（GAIA/RGB 对标中的 "Expecting value" ERROR），且工具结果无后处理
  （multi_01 输出 34.28 而非保留整数 34）。
- 新路径：工具 schema 走 LLM API 原生 function calling（DeepSeek 等支持），
  参数由 API 结构化返回（保证合法 JSON）；工具结果回传模型做"后处理回合"
  （格式化/取整/校验），失败自动重试。

用法：
    skill = FCToolSkill(
        llm=llm,
        name="calculator",
        description="安全计算数学表达式。参数: expr(str)",
        parameters={
            "type": "object",
            "properties": {"expr": {"type": "string"}},
            "required": ["expr"],
        },
        executor=tool_calculator,          # 同步或异步函数，参数按 schema 传入
        validator=None,                     # async (answer, task) -> (ok, feedback) | None
        max_retries=2,
    )
    result = await skill.run("计算 17*23+56")
    # result: {"answer": ..., "result": ..., "provider": "fc", "attempts": n}

也可以把 skill.run 包成 skill-agent handler 交给 CognitiveOrchestrator 调度。
"""
import inspect
import json
import logging

logger = logging.getLogger(__name__)


class FCToolSkill:
    def __init__(self, llm, name, description, parameters, executor,
                 validator=None, max_retries=2, postprocess_prompt=None):
        self.llm = llm
        self.name = name
        self.schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }
        self.executor = executor
        self.validator = validator
        self.max_retries = max_retries
        self.postprocess_prompt = postprocess_prompt or (
            "请根据工具结果给出最终答案。必须严格按任务要求处理结果"
            "（如保留整数、保留单位、格式化），只输出最终答案，不要解释。"
        )

    # ------------------------------------------------------------------
    async def _execute(self, args: dict):
        """执行工具：兼容同步与异步 executor。"""
        if inspect.iscoroutinefunction(self.executor):
            return await self.executor(**args)
        # 同步函数在事件循环里直接调用（工具都很轻，不阻塞）
        return self.executor(**args)

    # ------------------------------------------------------------------
    async def run(self, task: str, view=None) -> dict:
        """原生 function calling 闭环：FC 调用 → 工具执行 → 后处理 → 验证重试。"""
        messages = [
            {
                "role": "system",
                "content": (
                    "你是工具调用助手。先用函数调用获取工具结果，"
                    "再把工具结果按任务要求加工为最终答案。"
                ),
            },
            {"role": "user", "content": task},
        ]
        last_err = ""
        for attempt in range(self.max_retries + 1):
            try:
                calls, content = await self.llm.complete_with_tools(
                    messages, [self.schema], temperature=0.0, max_tokens=200
                )
            except NotImplementedError:
                # 降级：不支持原生 FC 的客户端走文本 JSON 解析
                return await self._run_text_fallback(task)

            if not calls:
                # 模型没调工具，直接给文本答案
                return {"answer": content, "provider": "fc-text", "attempts": attempt + 1}

            args = calls[0].get("arguments", {})
            try:
                result = await self._execute(args)
            except TypeError as e:
                last_err = f"工具参数错误: {e}"
                logger.warning(f"[FCToolSkill:{self.name}] {last_err}（重试）")
                messages.append({"role": "assistant", "content": f"工具参数错误: {e}"})
                messages.append({
                    "role": "user",
                    "content": f"工具 {self.name} 的参数不符合 schema，请按 schema 重新给出函数调用。",
                })
                continue
            except Exception as e:
                last_err = f"工具执行错误: {e}"
                messages.append({"role": "assistant", "content": f"工具执行失败: {e}"})
                messages.append({
                    "role": "user",
                    "content": f"工具执行失败，请重新尝试或换一种调用方式。",
                })
                continue

            # 后处理回合：工具结果交回模型，按任务要求产出最终答案
            # （必须带上原始任务，否则模型不知道格式化/取整等具体约束）
            messages.append({
                "role": "assistant",
                "content": f"工具 {self.name} 返回: {json.dumps(result, ensure_ascii=False, default=str)}",
            })
            post_messages = [
                {
                    "role": "system",
                    "content": (
                        "你是最终答案加工者。根据原始任务的要求，把工具结果加工为最终答案"
                        "（保留整数/保留单位/格式化等按任务要求执行）。只输出最终答案，不要解释。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"原始任务: {task}\n\n"
                        f"工具结果: {json.dumps(result, ensure_ascii=False, default=str)}\n\n"
                        "请严格按原始任务要求给出最终答案。"
                    ),
                },
            ]
            final = await self.llm.complete(
                post_messages, temperature=0.0, max_tokens=300
            )
            final = final.strip().strip("```").strip()

            if self.validator:
                ok, feedback = await self.validator(final, task)
                if not ok:
                    last_err = feedback
                    messages.append({"role": "assistant", "content": final})
                    messages.append({
                        "role": "user",
                        "content": f"最终答案不符合要求: {feedback}，请重新加工工具结果。",
                    })
                    continue

            return {
                "answer": final,
                "result": result,
                "provider": "fc",
                "attempts": attempt + 1,
            }

        return {"answer": f"ERROR: {last_err or '工具调用重试耗尽'}", "provider": "fc", "attempts": self.max_retries + 1}

    # ------------------------------------------------------------------
    async def _run_text_fallback(self, task: str) -> dict:
        """降级路径：文本 JSON 二次解析（兼容不支持原生 FC 的客户端）。"""
        prompt = (
            f"你是工具调用助手。根据任务调用 {self.name} 工具。\n"
            f"工具说明: {self.schema['function']['description']}\n"
            f"任务: {task}\n"
            "只输出 JSON 格式的参数对象，不要输出其他任何内容。"
        )
        resp = await self.llm.complete(
            [{"role": "user", "content": prompt}], temperature=0.0, max_tokens=200
        )
        resp = resp.strip().strip("```json").strip("```").strip()
        start, end = resp.find("{"), resp.rfind("}")
        if start == -1 or end == -1 or start > end:
            return {"answer": f"ERROR: 无法解析参数: {resp[:80]}", "provider": "text"}
        try:
            args = json.loads(resp[start:end + 1])
        except json.JSONDecodeError as e:
            return {"answer": f"ERROR: 参数JSON解析失败: {e}", "provider": "text"}
        try:
            result = await self._execute(args)
        except Exception as e:
            return {"answer": f"ERROR: 工具执行失败: {e}", "provider": "text"}
        return {"answer": str(result), "result": result, "provider": "text", "attempts": 1}
