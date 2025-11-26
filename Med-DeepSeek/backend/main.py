import os
import json
from typing import List, Optional, Literal, Dict, Any
import traceback

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv
from pathlib import Path

from db import engine, Base
import models  # 确保 ORM 模型注册到 Base
from session_store import SQLiteSessionStore  # 将来换 Redis 只改这一行即可

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import Response as FastAPIResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Medical Triage API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 开发阶段先用 *，确认能通
    allow_credentials=False,    # 用 * 时不要带 cookie
    allow_methods=["*"],        # 包括 OPTIONS
    allow_headers=["*"],
)


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
MAX_HISTORY_TURNS = 10          # 持久化里最多保留多少轮原始对话
RECENT_MESSAGE_LIMIT = 8        # 每次调用模型时，最多带多少条历史消息（user/assistant 混合）


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
    context_summary: Optional[str] = ""  # 模型维护的会话摘要
    disclaimer: str

class ResetSessionRequest(BaseModel):
    user_id: str



# ========= FastAPI App =========


def build_system_context(profile: Optional[PatientProfile], session_summary: str = "") -> str:
    """
    把患者档案 + 既往会话摘要 拼进 system 提示词中。
    """
    lines = [SYSTEM_PROMPT]

    if profile:
        lines.append("\n【患者基础信息】:")  # 单独一块
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

    if session_summary:
        lines.append("\n【既往问诊摘要】（供你参考，不要逐字复述）:")
        lines.append(session_summary)

    return "\n".join(lines)


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


@app.options("/api/consult")
async def options_consult():
    # 预检请求专用响应
    return FastAPIResponse(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.post("/api/consult", response_model=ConsultResponse)
async def consult(req: ConsultRequest, response: Response):
    """
    核心问诊接口（带自动摘要 + 长对话控制）：
    - 使用 context_summary 承接长历史
    - 每次只带最近 RECENT_MESSAGE_LIMIT 条原始对话
    """
    # 手动添加 CORS 头，确保浏览器可以访问
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"

    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id 不能为空，用于区分会话。")

    # 1. 从存储里读取会话（摘要 + 最近历史）
    session = session_store.get_session(req.user_id)
    session_summary: str = session.get("summary", "") or ""
    session_history: List[Dict[str, str]] = session.get("messages", []) or []

    # 2. 构造 system 提示词（含患者信息 + 既往会话摘要）
    system_content = build_system_context(req.patient_profile, session_summary)

    # 3. 控制上下文长度：只带最近 N 条消息
    if len(session_history) > RECENT_MESSAGE_LIMIT:
        recent_history = session_history[-RECENT_MESSAGE_LIMIT:]
    else:
        recent_history = session_history

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_content},
        *recent_history,
        {"role": "user", "content": req.query},
    ]

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
        traceback.print_exc()
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

    # 6. 安全兜底逻辑
    parsed = apply_safety_guard(parsed, user_query=req.query)

    # 7. 补齐字段
    parsed.setdefault("possible_diagnoses", [])
    parsed.setdefault("suggestions", [])
    parsed.setdefault("red_flags", [])
    parsed.setdefault("follow_up_questions", [])
    parsed.setdefault("context_summary", session_summary)  # 如果模型没给，则沿用旧摘要
    parsed.setdefault(
        "disclaimer",
        "本回答不能替代医生面诊和正规医疗服务，仅供一般健康信息参考。如症状明显、持续或加重，请尽快前往正规医疗机构就诊或拨打当地急救电话。"
    )
    if parsed.get("triage_level") not in ["emergency", "urgent", "non_urgent", "self_care", "unknown"]:
        parsed["triage_level"] = "unknown"

    # 8. 更新会话：摘要 + 原始对话
    new_summary: str = parsed.get("context_summary") or session_summary
    new_history = session_history + [
        {"role": "user", "content": req.query},
        {"role": "assistant", "content": parsed["answer"]},
    ]

    # 控制存储里的原始消息数量（防止 DB 无限涨）
    if len(new_history) > MAX_HISTORY_TURNS * 2:
        new_history = new_history[-MAX_HISTORY_TURNS * 2 :]

    session_store.save_session(req.user_id, new_summary, new_history)

    return parsed


@app.get("/api/session_status")
def session_status(user_id: str):
    """
    查询某个 user_id 的会话状态（是否存在、是否过期、历史条数等）
    """
    return session_store.get_status(user_id)


@app.post("/api/reset_session")
def reset_session(req: ResetSessionRequest, response: Response):
    """
    清空某个 user_id 的会话历史（用于“新开聊天”）。
    """
    # 可选：手动加一层 CORS 头（即使有全局 CORSMiddleware，也无伤大雅）
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"

    session_store.reset_session(req.user_id)
    return {
        "status": "ok",
        "message": f"session for user_id={req.user_id} has been reset"
    }
