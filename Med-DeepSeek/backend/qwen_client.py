import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "qwen3-vl-flash")

if not DASHSCOPE_API_KEY:
    raise RuntimeError("DASHSCOPE_API_KEY 未配置，请检查 .env")

qwen_client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
)

DEFAULT_SYSTEM_PROMPT = "你是一名严谨的中文智能医疗问诊助手，只能提供健康建议和就医建议，不能直接给出确诊结论。"


def build_messages(
    history_messages: Optional[List[Dict[str, Any]]],
    user_query: str,
    image_data_url: Optional[str] = None,
    system_prompt: Optional[str] = None,
):
    """
    兼容纯文本 / 图文多模态。image_data_url 形如 data:image/png;base64,xxxx
    """
    messages = [{"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT}]

    if history_messages:
        # 只允许 user/assistant，避免外部传进来 system 造成冲突
        for m in history_messages:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                messages.append({"role": role, "content": content})

    user_content = [{"type": "text", "text": user_query}]
    if image_data_url:
        user_content.append({"type": "image_url", "image_url": {"url": image_data_url}})

    messages.append({"role": "user", "content": user_content if image_data_url else user_query})
    return messages


def call_qwen3_max(
    user_query: str,
    history_messages=None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    image_data_url: Optional[str] = None,
    image_name: Optional[str] = None,
    system_prompt: Optional[str] = None,   # ✅ 新增
) -> str:
    if history_messages is None:
        history_messages = []

    messages = build_messages(
        history_messages,
        user_query,
        image_data_url=image_data_url,
        system_prompt=system_prompt,
    )

    resp = qwen_client.chat.completions.create(
        model=QWEN_MODEL_NAME,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return resp.choices[0].message.content.strip()
