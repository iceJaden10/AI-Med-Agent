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
    return "qwen"


def chat_with_llm(
    user_query: str,
    history_messages=None,
    provider: Optional[str] = None,
    image_data_url: Optional[str] = None,
    image_name: Optional[str] = None,
    system_prompt: Optional[str] = None,   # ✅ 新增
) -> tuple[str, ProviderType]:
    p = normalize_provider(provider)

    if p == "azure":
        if image_data_url:
            user_query = (
                f"{user_query}\n\n"
                "[User uploaded an image for reference, but the current model does not support image input. "
                "Please answer based on text only.]"
            )
        answer = call_azure_llm(user_query, history_messages, system_prompt=system_prompt)
    else:
        answer = call_qwen3_max(
            user_query,
            history_messages,
            image_data_url=image_data_url,
            image_name=image_name,
            system_prompt=system_prompt,
        )

    return answer, p
