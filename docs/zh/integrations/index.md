# 集成

HiveFlow 通过可选依赖组与 Studio 配置连接外部系统。

| 集成 | 包 extra | 文档 |
|-------------|---------------|-----|
| OpenAI | `hiveflow[llm]` | [OpenAI](openai.md) |
| Anthropic | `hiveflow[llm]` | [Anthropic](anthropic.md) |
| Redis（总线 / 黑板） | `hiveflow[redis]` | [Redis](redis.md) |
| PostgreSQL（Studio） | Studio backend deps | [PostgreSQL](postgres.md) |
| LangGraph（计划导出/导入） | Core adapter（无 extra） | [LangGraph PoC](langgraph.md) |

**完整指南：** [生态兼容指南（LangChain · LangGraph · MCP）](../guides/ecosystem-compatibility.md)

## 可选依赖组

```bash
pip install "hiveflow-core[security]"   # cryptography, jsonschema
pip install "hiveflow-core[redis]"      # redis
pip install "hiveflow-core[llm]"        # openai, anthropic
pip install "hiveflow-core[rag]"        # numpy, scikit-learn
pip install "hiveflow-core[all]"        # everything above
```

## 贡献新集成

1. 基于现有抽象实现（`LLMClient`、`BlackboardBackend`、`EventBus`、`MCPPluginManager`）
2. 在 `packages/core/pyproject.toml` 中添加可选依赖
3. 在 `docs/integrations/` 下新增页面，并从此索引链接
4. 在 `examples/` 下添加示例，并在 `run_smoke_tests.py` 中注册

PR 要求见 [CONTRIBUTING.md](https://github.com/jdidjhdh/hiveflow/blob/main/CONTRIBUTING.md)。
