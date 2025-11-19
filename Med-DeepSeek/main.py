import os
import json
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv
from pathlib import Path

from db import engine, Base
import models  # 确保 ORM 模型注册到 Base
from session_store import SQLiteSessionStore


# ========= 显式加载当前目录下的 .env =========
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_MODEL = os.getenv("AZURE_OPENAI_MODEL")

if not (AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_MODEL):
    raise RuntimeError(
        "请在 .env 中配置 AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY / AZURE_OPENAI_MODEL"
    )

AZURE_OPENAI_ENDPOINT = AZURE_OPENAI_ENDPOINT.rstrip("/")

# ========= 从单独文件加载 System Prompt =========
PROMPT_PATH = BASE_DIR / "system_prompt_medical_zh.txt"
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

# ========= 初始化数据库表 =========
Base.metadata.create_all(bind=engine)

# ========= 初始化会话存储 =========
session_store = SQLiteSessionStore()
MAX_HISTORY_TURNS = 10  # 最多保留 10 轮（user+assistant 共 20 条）


# ========= Pydantic 数据模型 =========

class PatientProfile(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None  # "男"/"女"/其他
    chronic_diseases: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    medications: Optional[List[str]] = None
    extra: Optional[Dict[str, Any]] = None  # 其他自定义信息


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ConsultRequest(BaseModel):
    user_id: Optional[str] = None
    query: str = Field(..., description="本轮用户的主诉/问题")
    history: List[ChatMessage] = Field(default_factory=list, description="历史对话（目前后端不依赖前端传）")
    patient_profile: Optional[PatientProfile] = None


class PossibleDiagnosis(BaseModel):
    name: str
    probability: float


class ConsultResponse(BaseModel):
    answer: str
    triage_level: Literal["emergency", "urgent", "non_urgent", "self_care", "unknown"]
    possible_diagnoses: List[PossibleDiagnosis]
    suggestions: List[str]
    red_flags: List[str]
    follow_up_questions: List[str]
    context_summary: Optional[str] = ""  # 给默认值，防止模型漏字段时报错
    disclaimer: str


# ========= FastAPI App =========

app = FastAPI(title="Medical Triage API", version="0.2.0")


def build_system_context(profile: Optional[PatientProfile]) -> str:
    """
    把患者档案信息拼进 system 提示词中，提升问诊准确度。
    """
    if not profile:
        return SYSTEM_PROMPT

    lines = ["\n【患者基础信息】:"]
    if profile.age is not None:
        lines.append(f"- 年龄: {profile.age} 岁")
    if profile.gender:
        lines.append(f"- 性别: {profile.gender}")
    if profile.chronic_diseases:
        lines.append(f"- 慢性疾病: {', '.join(profile.chronic_diseases)}")
    if profile.allergies:
        lines.append(f"- 过敏史: {', '.join(profile.allergies)}")
    if profile.medications:
        lines.append(f"- 正在使用的药物: {', '.join(profile.medications)}")
    if profile.extra:
        lines.append(f"- 其他: {profile.extra}")

    return SYSTEM_PROMPT + "\n" + "\n".join(lines)


def apply_safety_guard(parsed: Dict[str, Any], user_query: str) -> Dict[str, Any]:
    emergency_keywords = [
        "胸痛", "胸口疼", "胸闷", "呼吸困难", "喘不过气", "大出血", "喷射状呕吐",
        "昏迷", "意识不清", "抽搐", "癫痫", "自杀", "想死", "跳楼",
        "高烧不退", "39度以上", "40度", "心梗", "中风", "半身无力"
    ]

    text = user_query or ""
    is_emergency = any(k in text for k in emergency_keywords)

    triage = parsed.get("triage_level", "unknown")
    if triage not in ["emergency", "urgent", "non_urgent", "self_care", "unknown"]:
        triage = "unknown"

    if is_emergency:
        triage = "emergency"
        red_flags = parsed.get("red_flags") or []
        red_flags.append("根据您描述的症状，存在可能危及生命的风险，建议立刻前往急诊或拨打当地急救电话。")
        parsed["red_flags"] = red_flags

    parsed["triage_level"] = triage
    return parsed


@app.post("/api/consult", response_model=ConsultResponse)
async def consult(req: ConsultRequest):
    """
    核心问诊接口：
    - 基于 user_id 的多轮对话：后端自动维护历史（SQLite 持久化）
    """
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id 不能为空，用于区分会话。")

    # 1. 构造 system 提示词（含患者基础信息）
    system_content = build_system_context(req.patient_profile)

    # 2. 从持久化存储中读取历史对话
    session_history = session_store.get_history(req.user_id)

    # 3. 组装 messages：System + 历史 + 当前用户消息
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_content},
    ]
    messages.extend(session_history)
    messages.append({"role": "user", "content": req.query})

    # 4. 调用 Azure AI Foundry
    url = f"{AZURE_OPENAI_ENDPOINT}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_API_KEY,
        "Authorization": f"Bearer {AZURE_OPENAI_API_KEY}",
    }
    payload = {
        "model": AZURE_OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"调用模型失败: {str(e)}")

    data = resp.json()
    try:
        model_text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise HTTPException(status_code=500, detail=f"模型返回格式异常: {str(e)}")

    # 5. 解析模型返回的 JSON
    try:
        parsed = json.loads(model_text)
    except json.JSONDecodeError:
        parsed = {
            "answer": "抱歉，系统暂时无法稳定解析智能问诊结果。建议您尽快前往线下正规医疗机构就诊或拨打当地急救电话获取帮助。",
            "triage_level": "unknown",
            "possible_diagnoses": [],
            "suggestions": [],
            "red_flags": [],
            "follow_up_questions": [],
            "context_summary": "",
            "disclaimer": "本回答不能替代医生面诊和正规医疗服务，仅供一般健康信息参考。如症状明显、持续或加重，请尽快前往正规医疗机构就诊或拨打当地急救电话。"
        }

    # 6. 安全兜底逻辑（关键词 → 强制提升 triage）
    parsed = apply_safety_guard(parsed, user_query=req.query)

    # 7. 补齐字段
    parsed.setdefault("possible_diagnoses", [])
    parsed.setdefault("suggestions", [])
    parsed.setdefault("red_flags", [])
    parsed.setdefault("follow_up_questions", [])
    parsed.setdefault("context_summary", "")
    parsed.setdefault(
        "disclaimer",
        "本回答不能替代医生面诊和正规医疗服务，仅供一般健康信息参考。如症状明显、持续或加重，请尽快前往正规医疗机构就诊或拨打当地急救电话。"
    )
    if parsed.get("triage_level") not in ["emergency", "urgent", "non_urgent", "self_care", "unknown"]:
        parsed["triage_level"] = "unknown"

    # 8. 把当前这一轮写入会话历史（只存“对话内容”，方便下一轮）
    history = session_history or []
    history.append({"role": "user", "content": req.query})
    history.append({"role": "assistant", "content": parsed["answer"]})

    # 控制历史长度，防止无限增长
    if len(history) > MAX_HISTORY_TURNS * 2:
        history = history[-MAX_HISTORY_TURNS * 2 :]

    # 写回持久化存储
    session_store.save_history(req.user_id, history)

    return parsed


@app.get("/api/session_status")
def session_status(user_id: str):
    """
    查询某个 user_id 的会话状态（是否存在、是否过期、历史条数等）
    """
    return session_store.get_status(user_id)


@app.post("/api/reset_session")
def reset_session(user_id: str):
    """
    清空某个 user_id 的会话历史。
    """
    session_store.reset_session(user_id)
    return {"status": "ok", "message": f"session for user_id={user_id} has been reset"}
