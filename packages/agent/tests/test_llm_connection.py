"""LLM 连接测试脚本 - 快速验证 LLM 配置是否正确。

用法:
  python tests/test_llm_connection.py          # 自动检测提供商
  python tests/test_llm_connection.py openai   # 指定提供商
  python tests/test_llm_connection.py deepseek
  python tests/test_llm_connection.py anthropic
  python tests/test_llm_connection.py ollama

环境变量:
  LLM_PROVIDER, OPENAI_API_KEY, DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, LLM_MODEL
"""
import asyncio
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from llm.provider_factory import create_llm_client, get_provider_info, list_available_providers


@pytest.mark.asyncio
async def test_connection():
    """测试 LLM 连接。"""
    # 指定提供商
    provider_arg = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 60)
    print("HiveFlow Agent - LLM 连接测试")
    print("=" * 60)

    # 显示可用提供商
    available = list_available_providers()
    print(f"\n可用提供商: {available or '无'}")

    # 显示当前配置
    info = get_provider_info(provider_arg)
    print(f"选定提供商: {info['provider']}")
    print(f"使用模型: {info['model']}")
    print(f"API key 已设置: {info['api_key_set']}")

    if not available:
        print("\n错误: 没有可用的 LLM 提供商")
        print("请设置以下环境变量之一:")
        print("  LLM_PROVIDER=openai  + OPENAI_API_KEY")
        print("  LLM_PROVIDER=deepseek + DEEPSEEK_API_KEY")
        print("  LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY")
        print("  LLM_PROVIDER=ollama (不需要 API key)")
        return False

    print("\n正在测试连接...")

    try:
        llm = create_llm_client(provider_arg)

        # 测试简单对话
        messages = [
            {"role": "system", "content": "你是一个测试助手。请回复 'OK'。"},
            {"role": "user", "content": "测试连接"}
        ]

        response = await llm.complete(messages)
        print(f"响应: {response[:100]}")

        # 测试 JSON 解析
        json_messages = [
            {"role": "system", "content": "你是一个 JSON 生成器。请返回纯 JSON 格式，不要使用 markdown。"},
            {"role": "user", "content": '返回 {"status": "ok", "message": "test passed"}'}
        ]

        result = await llm.complete_json(json_messages)
        print(f"JSON 解析: {result}")

        print("\n" + "=" * 60)
        print("✅ LLM 连接测试通过!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ LLM 连接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
