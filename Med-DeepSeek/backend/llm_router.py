# backend/llm_router.py
import os
from typing import Literal, Optional

from azure_client import call_azure_llm
from qwen_client import call_qwen3_max

ProviderType = Literal["azure", "qwen"]

DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "qwen").lower()


def normalize_provider(provider: Optional[str]) -> ProviderType:
    p = (provider or DEFAULT_PROVIDER).lower()
    if p in ("azure", "az", "azure_openai"):
        return "azure"
    if p in ("qwen", "qwen3", "qwen3-max", "ali", "aliyun"):
        return "qwen"
    return "qwen"   # 不识别时默认 Qwen


def chat_with_llm(
    user_query: str,
    history_messages=None,
    provider: Optional[str] = None,
) -> tuple[str, ProviderType]:
    """
    返回：(answer, actual_provider)
    provider:
      - None: 使用 .env 的 LLM_PROVIDER
      - "azure": 强制 Azure
      - "qwen":  强制 Qwen3-max
    """
    p = normalize_provider(provider)

    if p == "azure":
        answer = call_azure_llm(user_query, history_messages)
    else:
        answer = call_qwen3_max(user_query, history_messages)

    return answer, p
