# backend/azure_client.py
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")  # 末尾带不带 / 都没事
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_MODEL = os.getenv("AZURE_OPENAI_MODEL", "DeepSeek-v3.1")

if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
    raise RuntimeError("Azure OpenAI 配置缺失，请检查 .env 中的 AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY")

azure_client = OpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    base_url=AZURE_OPENAI_ENDPOINT,  # 你的 endpoint 已经到 /openai/v1/ 了
)


def call_azure_llm(user_query: str, history_messages=None) -> str:
    """
    用 Azure OpenAI（DeepSeek）生成回复。
    history_messages：形如 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    if history_messages is None:
        history_messages = []

    messages = [
        {"role": "system", "content": "你是一名严谨的中文智能医疗问诊助手（Azure DeepSeek 版本）。"},
        *history_messages,
        {"role": "user", "content": user_query},
    ]

    resp = azure_client.chat.completions.create(
        model=AZURE_OPENAI_MODEL,
        messages=messages,
        temperature=0.2,
        max_tokens=1024,
    )

    return resp.choices[0].message.content.strip()
