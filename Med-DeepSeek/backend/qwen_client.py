# backend/qwen_client.py
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "qwen3-max")

if not DASHSCOPE_API_KEY:
    raise RuntimeError("DASHSCOPE_API_KEY 未配置，请检查 .env")

qwen_client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
)

SYSTEM_PROMPT_PATH = BASE_DIR / "system_prompt_medical_zh.txt"
if SYSTEM_PROMPT_PATH.exists():
    SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
else:
    SYSTEM_PROMPT = "你是一名严谨的中文智能医疗问诊助手，只能提供健康建议和就医建议，不能直接给出确诊结论。"


def build_messages(history_messages, user_query: str):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": user_query})
    return messages


def call_qwen3_max(
    user_query: str,
    history_messages=None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    if history_messages is None:
        history_messages = []

    messages = build_messages(history_messages, user_query)

    resp = qwen_client.chat.completions.create(
        model=QWEN_MODEL_NAME,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return resp.choices[0].message.content.strip()
