import json
import traceback
import inspect
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response as FastAPIResponse

from dotenv import load_dotenv

from db import engine, Base
import models  # noqa: F401  确保 ORM 模型注册到 Base
from session_store import SQLiteSessionStore

from llm_router import chat_with_llm


# =========================
# App & Config
# =========================

app = FastAPI(title="Medical Triage API", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# CORS（生产建议用环境变量控制）
# 例：ALLOW_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
import os
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*")
ALLOW_ORIGINS_LIST = ["*"] if ALLOW_ORIGINS.strip() == "*" else [x.strip() for x in ALLOW_ORIGINS.split(",") if x.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS_LIST,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prompts
PROMPT_ZH_PATH = BASE_DIR / "system_prompt_medical_zh.txt"
PROMPT_EN_PATH = BASE_DIR / "system_prompt_medical_en.txt"

if not PROMPT_ZH_PATH.exists():
    raise RuntimeError(f"Missing prompt: {PROMPT_ZH_PATH}")

SYSTEM_PROMPT_ZH = PROMPT_ZH_PATH.read_text(encoding="utf-8")
SYSTEM_PROMPT_EN = PROMPT_EN_PATH.read_text(encoding="utf-8") if PROMPT_EN_PATH.exists() else SYSTEM_PROMPT_ZH

# DB init
Base.metadata.create_all(bind=engine)

# Session store
session_store = SQLiteSessionStore()
MAX_HISTORY_TURNS = 10
RECENT_MESSAGE_LIMIT = 8


# =========================
# Pydantic Models
# =========================

class PatientProfile(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    chronic_diseases: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    medications: Optional[List[str]] = None
    extra: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ConsultRequest(BaseModel):
    user_id: Optional[str] = None
    query: str = Field(..., description="本轮用户的主诉/问题")
    history: List[ChatMessage] = Field(default_factory=list, description="历史对话（目前后端不依赖前端传）")
    patient_profile: Optional[PatientProfile] = None
    provider: Optional[str] = Field(default=None, description="可选：'qwen' 或 'azure'")
    image_base64: Optional[str] = None
    image_mime_type: Optional[str] = None
    image_name: Optional[str] = None
    lang: Optional[Literal["zh", "en"]] = "zh"


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
    context_summary: Optional[str] = ""
    disclaimer: str


class ResetSessionRequest(BaseModel):
    user_id: str


# =========================
# i18n Fallback Text
# =========================

DISCLAIMER_ZH = "本回答不能替代医生面诊和正规医疗服务，仅供一般健康信息参考。如症状明显、持续或加重，请尽快前往正规医疗机构就诊或拨打当地急救电话。"
DISCLAIMER_EN = "This response is not a substitute for professional medical diagnosis or treatment. It is for general health information only. If symptoms are severe, persistent, or worsening, seek in-person care or call local emergency services."

PARSE_FALLBACK_ZH = {
    "answer": "抱歉，系统暂时无法稳定解析智能问诊结果。建议您尽快前往线下正规医疗机构就诊或拨打当地急救电话获取帮助。",
    "triage_level": "unknown",
    "possible_diagnoses": [],
    "suggestions": [],
    "red_flags": [],
    "follow_up_questions": [],
    "context_summary": "",
    "disclaimer": DISCLAIMER_ZH,
}
PARSE_FALLBACK_EN = {
    "answer": "Sorry, the system couldn't reliably parse the triage result. Please seek in-person medical care or call local emergency services if needed.",
    "triage_level": "unknown",
    "possible_diagnoses": [],
    "suggestions": [],
    "red_flags": [],
    "follow_up_questions": [],
    "context_summary": "",
    "disclaimer": DISCLAIMER_EN,
}


# =========================
# Helpers
# =========================

def normalize_lang(lang: Optional[str]) -> Literal["zh", "en"]:
    return "en" if (lang or "").lower() == "en" else "zh"


def load_base_prompt(lang: Literal["zh", "en"]) -> str:
    return SYSTEM_PROMPT_EN if lang == "en" else SYSTEM_PROMPT_ZH


def language_strict_rule(lang: Literal["zh", "en"]) -> str:
    # 再加一道“硬约束”，避免模型跑偏/夹杂
    if lang == "en":
        return (
            "\n[STRICT OUTPUT RULE]\n"
            "- You MUST respond in English only.\n"
            "- All JSON string fields MUST be English only. Do NOT mix Chinese.\n"
            "- Return ONLY valid JSON. No markdown.\n"
        )
    return (
        "\n【强制输出规则】\n"
        "- 你必须只用简体中文输出。\n"
        "- JSON 的所有字符串字段必须为简体中文，不得夹杂英文。\n"
        "- 只输出合法 JSON，不要输出 Markdown。\n"
    )


def build_system_context(profile: Optional[PatientProfile], session_summary: str, lang: Literal["zh", "en"]) -> str:
    lines: List[str] = [load_base_prompt(lang).strip(), language_strict_rule(lang)]

    if profile:
        if lang == "en":
            lines.append("\n[Patient profile]:")
            if profile.age is not None:
                lines.append(f"- Age: {profile.age}")
            if profile.gender:
                lines.append(f"- Gender: {profile.gender}")
            if profile.chronic_diseases:
                lines.append(f"- Chronic conditions: {', '.join(profile.chronic_diseases)}")
            if profile.allergies:
                lines.append(f"- Allergies: {', '.join(profile.allergies)}")
            if profile.medications:
                lines.append(f"- Current medications: {', '.join(profile.medications)}")
            if profile.extra:
                lines.append(f"- Extra: {profile.extra}")
        else:
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
        if lang == "en":
            lines.append("\n[Conversation summary] (for reference, do not repeat verbatim):")
            lines.append(session_summary)
        else:
            lines.append("\n【既往问诊摘要】（供你参考，不要逐字复述）:")
            lines.append(session_summary)

    return "\n".join(lines).strip()


def build_image_data_url(image_base64: Optional[str], mime: Optional[str]) -> Optional[str]:
    if not image_base64:
        return None
    safe_mime = mime if (mime and "/" in mime) else "image/jpeg"
    return f"data:{safe_mime};base64,{image_base64}"


def apply_safety_guard(parsed: Dict[str, Any], user_query: str, lang: Literal["zh", "en"]) -> Dict[str, Any]:
    emergency_keywords_zh = [
        "胸痛", "胸口疼", "胸闷", "呼吸困难", "喘不过气", "大出血", "喷射状呕吐",
        "昏迷", "意识不清", "抽搐", "癫痫", "自杀", "想死", "跳楼",
        "高烧不退", "39度以上", "40度", "心梗", "中风", "半身无力"
    ]
    emergency_keywords_en = [
        "chest pain", "tight chest", "shortness of breath", "can't breathe", "massive bleeding",
        "vomiting blood", "loss of consciousness", "seizure", "suicide", "high fever", "stroke",
        "one-sided weakness"
    ]

    text_raw = user_query or ""
    text_lower = text_raw.lower()

    is_emergency = any(k in text_lower for k in emergency_keywords_en) if lang == "en" else any(k in text_raw for k in emergency_keywords_zh)

    triage = parsed.get("triage_level", "unknown")
    if triage not in ["emergency", "urgent", "non_urgent", "self_care", "unknown"]:
        triage = "unknown"

    if is_emergency:
        triage = "emergency"
        red_flags = parsed.get("red_flags") or []
        if lang == "en":
            red_flags.append("Based on your symptoms, there may be a life-threatening risk. Go to the ER immediately or call local emergency services.")
        else:
            red_flags.append("根据您描述的症状，存在可能危及生命的风险，建议立刻前往急诊或拨打当地急救电话。")
        parsed["red_flags"] = red_flags

    parsed["triage_level"] = triage
    return parsed


def ensure_schema(parsed: Dict[str, Any], lang: Literal["zh", "en"], session_summary: str) -> Dict[str, Any]:
    parsed.setdefault("possible_diagnoses", [])
    parsed.setdefault("suggestions", [])
    parsed.setdefault("red_flags", [])
    parsed.setdefault("follow_up_questions", [])
    parsed.setdefault("context_summary", session_summary)
    parsed.setdefault("disclaimer", DISCLAIMER_EN if lang == "en" else DISCLAIMER_ZH)

    triage = parsed.get("triage_level")
    if triage not in ["emergency", "urgent", "non_urgent", "self_care", "unknown"]:
        parsed["triage_level"] = "unknown"

    if "answer" not in parsed or not isinstance(parsed["answer"], str):
        parsed["answer"] = PARSE_FALLBACK_EN["answer"] if lang == "en" else PARSE_FALLBACK_ZH["answer"]

    return parsed


# =========================
# Routes
# =========================

@app.options("/api/consult")
async def options_consult():
    return FastAPIResponse(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*" if "*" in ALLOW_ORIGINS_LIST else ",".join(ALLOW_ORIGINS_LIST),
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.post("/api/consult", response_model=ConsultResponse)
async def consult(req: ConsultRequest, response: Response):
    # CORS 头（某些代理/部署环境更稳）
    response.headers["Access-Control-Allow-Origin"] = "*" if "*" in ALLOW_ORIGINS_LIST else ",".join(ALLOW_ORIGINS_LIST)
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"

    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id 不能为空，用于区分会话。")

    lang = normalize_lang(req.lang)

    # 1) load session
    session = session_store.get_session(req.user_id)
    session_summary: str = session.get("summary", "") or ""
    session_history: List[Dict[str, str]] = session.get("messages", []) or []

    # 2) build system prompt with lang
    system_content = build_system_context(req.patient_profile, session_summary, lang)

    # 3) recent history
    recent_history = session_history[-RECENT_MESSAGE_LIMIT:] if len(session_history) > RECENT_MESSAGE_LIMIT else session_history

    # 4) image
    image_data_url = build_image_data_url(req.image_base64, req.image_mime_type)

    # 5) call llm_router
    # 关键点：你之前只把 recent_history 传给 router，system prompt 没进去
    # 这里把 system 作为 history 第一条塞进去，保证模型遵守语言/JSON 规则
    router_history = [{"role": "system", "content": system_content}, *recent_history]

    try:
        result = chat_with_llm(
            user_query=req.query,
            history_messages=recent_history,
            provider=req.provider,
            image_data_url=image_data_url,
            image_name=req.image_name,
            system_prompt=system_content, 
        )

        if inspect.isawaitable(result):
            result = await result

        model_text = result[0] if isinstance(result, tuple) else result

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"调用模型失败: {str(e)}")

    # 6) parse json
    try:
        parsed = json.loads(model_text)
    except json.JSONDecodeError:
        parsed = PARSE_FALLBACK_EN.copy() if lang == "en" else PARSE_FALLBACK_ZH.copy()

    # 7) safety + schema
    parsed = apply_safety_guard(parsed, user_query=req.query, lang=lang)
    parsed = ensure_schema(parsed, lang=lang, session_summary=session_summary)

    # 8) update session
    new_summary: str = parsed.get("context_summary") or session_summary
    new_history = session_history + [
        {"role": "user", "content": req.query},
        {"role": "assistant", "content": parsed.get("answer", "")},
    ]

    if len(new_history) > MAX_HISTORY_TURNS * 2:
        new_history = new_history[-MAX_HISTORY_TURNS * 2:]

    session_store.save_session(req.user_id, new_summary, new_history)

    return parsed


@app.get("/api/session_status")
def session_status(user_id: str):
    return session_store.get_status(user_id)


@app.post("/api/reset_session")
def reset_session(req: ResetSessionRequest, response: Response):
    response.headers["Access-Control-Allow-Origin"] = "*" if "*" in ALLOW_ORIGINS_LIST else ",".join(ALLOW_ORIGINS_LIST)
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"

    session_store.reset_session(req.user_id)
    return {"status": "ok", "message": f"session for user_id={req.user_id} has been reset"}
