"""HiveFlow Agent - LLM 提供商工厂

支持多种 LLM 提供商的自动配置:
- OpenAI (gpt-4o, gpt-4, gpt-3.5-turbo)
- DeepSeek (deepseek-chat, deepseek-coder)
- Anthropic Claude (claude-3-opus, claude-3-sonnet, claude-3-haiku)
- Ollama (本地部署，支持 llama3, mistral, qwen 等)

环境变量配置:
  LLM_PROVIDER: 提供商名称 (openai, deepseek, anthropic, ollama)
  OPENAI_API_KEY: OpenAI API key
  DEEPSEEK_API_KEY: DeepSeek API key (或使用 OPENAI_API_KEY)
  ANTHROPIC_API_KEY: Anthropic API key
  LLM_MODEL: 模型名称 (可选，默认使用各提供商的推荐模型)
  LLM_BASE_URL: 自定义 base_url (可选)
  OLLAMA_BASE_URL: Ollama 服务地址 (默认 http://localhost:11434)
"""
import os
from .base import LLMClient


def create_llm_client(provider: str = None, **kwargs) -> LLMClient:
    """创建 LLM 客户端，自动检测或指定提供商。

    Args:
        provider: 提供商名称 (openai, deepseek, anthropic, ollama)
                 如果不指定，按以下优先级自动检测:
                 1. LLM_PROVIDER 环境变量
                 2. 可用的 API key
        **kwargs: 传递给具体客户端的额外参数
                 - model: 模型名称
                 - api_key: API key
                 - base_url: 自定义 base_url

    Returns:
        LLMClient 实例

    Raises:
        ValueError: 无法确定提供商或缺少 API key
        ImportError: 所需的包未安装
    """
    # 确定提供商
    if not provider:
        provider = os.environ.get("LLM_PROVIDER", "").lower()

    if not provider:
        # 自动检测可用的 API key
        if os.environ.get("DEEPSEEK_API_KEY"):
            provider = "deepseek"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        elif os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        else:
            # 尝试 Ollama (本地部署，不需要 API key)
            provider = "ollama"

    provider = provider.lower()

    # 获取模型名称
    model = kwargs.pop("model", None) or os.environ.get("LLM_MODEL")

    # 根据提供商创建对应客户端
    if provider == "openai":
        return _create_openai_client(model, **kwargs)
    elif provider == "deepseek":
        return _create_deepseek_client(model, **kwargs)
    elif provider == "anthropic":
        return _create_anthropic_client(model, **kwargs)
    elif provider == "ollama":
        return _create_ollama_client(model, **kwargs)
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Supported: openai, deepseek, anthropic, ollama"
        )


def _create_openai_client(model: str = None, **kwargs) -> LLMClient:
    """创建 OpenAI 客户端"""
    from .openai_client import OpenAILLMClient

    model = model or os.environ.get("LLM_MODEL", "gpt-4o")
    api_key = kwargs.pop("api_key", None)
    base_url = kwargs.pop("base_url", os.environ.get("OPENAI_BASE_URL"))

    return OpenAILLMClient(model=model, api_key=api_key, base_url=base_url, **kwargs)


def _create_deepseek_client(model: str = None, **kwargs) -> LLMClient:
    """创建 DeepSeek 客户端"""
    from .deepseek_client import DeepSeekLLMClient

    model = model or os.environ.get("LLM_MODEL", "deepseek-chat")
    api_key = kwargs.pop("api_key", None)
    base_url = kwargs.pop("base_url", os.environ.get("DEEPSEEK_BASE_URL"))

    return DeepSeekLLMClient(model=model, api_key=api_key, base_url=base_url, **kwargs)


def _create_anthropic_client(model: str = None, **kwargs) -> LLMClient:
    """创建 Anthropic Claude 客户端"""
    from .anthropic_client import AnthropicLLMClient

    model = model or os.environ.get("LLM_MODEL", "claude-3-5-sonnet-20241022")
    api_key = kwargs.pop("api_key", None)

    return AnthropicLLMClient(model=model, api_key=api_key, **kwargs)


def _create_ollama_client(model: str = None, **kwargs) -> LLMClient:
    """创建 Ollama 本地客户端"""
    from .ollama_client import OllamaLLMClient

    model = model or os.environ.get("LLM_MODEL", "llama3")
    base_url = kwargs.pop("base_url", os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))

    return OllamaLLMClient(model=model, base_url=base_url, **kwargs)


def list_available_providers() -> list:
    """列出当前环境中可用的 LLM 提供商。

    Returns:
        可用的提供商名称列表
    """
    available = []

    # 检查 Ollama (不需要 API key)
    try:
        from .ollama_client import OllamaLLMClient
        available.append("ollama")
    except ImportError:
        pass

    # 检查 OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from .openai_client import OpenAILLMClient
            available.append("openai")
        except ImportError:
            pass

    # 检查 DeepSeek
    if os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        try:
            from .deepseek_client import DeepSeekLLMClient
            available.append("deepseek")
        except ImportError:
            pass

    # 检查 Anthropic
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from .anthropic_client import AnthropicLLMClient
            available.append("anthropic")
        except ImportError:
            pass

    return available


def get_provider_info(provider: str = None) -> dict:
    """获取指定提供商的信息。

    Returns:
        包含 provider, model, api_key_set, available_providers 的字典
    """
    if not provider:
        provider = os.environ.get("LLM_PROVIDER", "auto")

    model = os.environ.get("LLM_MODEL", "default")

    # 默认模型
    default_models = {
        "openai": "gpt-4o",
        "deepseek": "deepseek-chat",
        "anthropic": "claude-3-5-sonnet-20241022",
        "ollama": "llama3",
    }

    if provider != "auto" and provider in default_models:
        model = model or default_models[provider]
    elif provider == "auto":
        available = list_available_providers()
        provider = available[0] if available else "none"
        model = default_models.get(provider, "unknown")

    return {
        "provider": provider,
        "model": model,
        "api_key_set": bool(
            os.environ.get("OPENAI_API_KEY") or
            os.environ.get("DEEPSEEK_API_KEY") or
            os.environ.get("ANTHROPIC_API_KEY")
        ),
        "available_providers": list_available_providers(),
    }
