import os
import json
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv

# 读取 .env
load_dotenv()

# ========= 从 .env 中读取 Azure AI Foundry 配置 =========
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")  # 例如: https://med-deepseek-resource.openai.azure.com/openai/v1
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_MODEL = os.getenv("AZURE_OPENAI_MODEL")        # 例如: deepseek-v3

if not (AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_MODEL):
    raise RuntimeError(
        "请在 .env 中配置 AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY / AZURE_OPENAI_MODEL"
    )

# 去掉尾部多余的斜杠，防止拼出 //chat/completions
AZURE_OPENAI_ENDPOINT = AZURE_OPENAI_ENDPOINT.rstrip("/")

# ========= System Prompt（问诊规范 + JSON 输出要求） =========

SYSTEM_PROMPT = """
你是一个面向普通用户的中文智能医疗分诊助手，擅长根据患者自述症状给出【风险评估、就医紧急程度和基础健康建议】。

【重要原则】：
1. 你不是医生，不能做出“确诊”，只能给出“可能的情况”和“建议尽快就医”。
2. 不能开具处方、不能给出详细剂量（例如：具体多少毫克、几片、多久一次），可以给出药物类别级别的建议（如“解热镇痛药”“生理盐水冲洗”等）。
3. 对明显高危情况（如：胸痛、呼吸困难、持续抽搐、意识模糊、大出血、自杀念头、高烧不退且精神差、严重外伤等），一定要优先提醒用户立刻线下或急诊就医。
4. 可能涉及隐私和敏感内容时，要提醒用户避免透露真实姓名、身份证号、详细地址等个人信息。

【输入信息】：
- 用户会用自然语言描述自己的症状、持续时间、既往病史等。
- 可能额外传入患者基本信息（如：年龄、性别、身高体重、基础疾病、用药史、过敏史等）。

【输出格式要求（务必严格遵守）】：
你必须 只返回 JSON，不要包含任何解释性文字、不要写在代码块里，不要带前后缀。
JSON 结构如下（字段名必须一致）：

{
  "answer": "用日常口语、易懂的方式，给用户的一段整体回复，建议控制在 300-600 字左右。",
  "triage_level": "emergency | urgent | non_urgent | self_care",
  "possible_diagnoses": [
    {
      "name": "可能的疾病或问题名称（例如：急性胃肠炎，上呼吸道感染，偏头痛等，不能写“确诊”）",
      "probability": 0.6
    }
  ],
  "suggestions": [
    "3-6 条具体可执行的建议，例如是否需要线下就诊、建议挂什么科、在家可以做的对症处理注意事项等。"
  ],
  "red_flags": [
    "列出 0-5 条需要特别注意的“危险信号”（如症状加重、出现哪些新症状时要立刻就医）。如果没有可留空数组。"
  ],
  "follow_up_questions": [
    "2-5 个为了进一步判断而希望向用户追问的关键问题（例如：症状持续多久、有没有发烧、是否有基础病等）。"
  ],
  "disclaimer": "本回答不能替代医生面诊和正规医疗服务，仅供一般健康信息参考。如症状明显、持续或加重，请尽快前往正规医疗机构就诊或拨打当地急救电话。"
}

【字段含义说明】：
- triage_level 取值说明：
  - "emergency": 可能存在严重或危及生命的情况，建议立刻急诊或拨打当地急救电话。
  - "urgent": 建议尽快（通常 24 小时内）到线下就诊。
  - "non_urgent": 需要就医，但一般可以在几天内安排普通门诊。
  - "self_care": 暂时可以在家观察和简单处理，但要结合 red_flags 提醒何时需要就医。
- possible_diagnoses：
  - 最多给出 3-5 个；
  - probability 为 0~1 之间的小数，代表“相对可能性”，总和不必严格等于 1。
  - 描述时避免绝对化用语（例如用“可能”“倾向于”而不是“就是”“一定是”）。
- suggestions：
  - 建议包括：是否、何时需要就医，建议就诊科室（例如：内科、儿科、皮肤科、急诊等），以及在家可尝试的护理措施和注意事项。
- red_flags：
  - 如果当前就已经符合急诊指征，也要在这里重复提示，并与 triage_level 保持一致。
- follow_up_questions：
  - 用以引导用户补充更关键信息，有助于下一轮回答更准确。

【安全与合规要求】：
1. 对于用户要求“帮我确诊”“一定是什么病”“给我具体药名和剂量”的请求，要在 answer 中明确说明你不能做确诊或给具体处方剂量。
2. 对于明显需要急诊的情况，即便用户没有主动要求，你也要在 answer 和 red_flags 中主动提醒，并设置 triage_level = "emergency"。
3. 需要鼓励用户寻求线下专业帮助，尤其是孕妇、儿童、老年人、多基础疾病人群或症状持续时间较长者。

【格式检查】：
- 不要输出注释，不要输出多余的字段。
- 不要在 JSON 外多写任何文字（包括“下面是 JSON”之类的说明）。
- 如果对信息严重不足无法判断，也要照样输出完整的 JSON，只是在各字段中说明“信息不足，需要补充 xxx”。
"""


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
    history: List[ChatMessage] = Field(default_factory=list, description="历史对话，用于多轮问诊")
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
    disclaimer: str


# ========= FastAPI App =========

app = FastAPI(title="Medical Triage API", version="0.1.0")


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
    """
    安全兜底：根据关键词强制提升急诊等级；同时修正 triage_level 异常值。
    """
    emergency_keywords = [
        "胸痛", "胸口疼", "胸闷", "呼吸困难", "喘不过气", "大出血", "喷射状呕吐",
        "昏迷", "意识不清", "抽搐", "癫痫", "自杀", "想死", "跳楼",
        "高烧不退", "39度以上", "40度", "心梗", "中风", "半身无力"
    ]

    text = (user_query or "") + " " + (parsed.get("answer") or "")
    is_emergency = any(k in text for k in emergency_keywords)

    triage = parsed.get("triage_level", "unknown")
    if triage not in ["emergency", "urgent", "non_urgent", "self_care"]:
        triage = "unknown"

    if is_emergency:
        triage = "emergency"
        red_flags = parsed.get("red_flags") or []
        red_flags.append("根据症状描述，存在可能危及生命的风险，建议立刻前往急诊或拨打当地急救电话。")
        parsed["red_flags"] = red_flags

    parsed["triage_level"] = triage
    return parsed


@app.post("/api/consult", response_model=ConsultResponse)
async def consult(req: ConsultRequest):
    """
    核心问诊接口：
    - 输入：query + history + patient_profile
    - 输出：结构化 JSON（由 DeepSeek 生成，后端加一层安全兜底）
    """
    # 1. 组装 messages
    system_content = build_system_context(req.patient_profile)

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_content},
    ]

    for msg in req.history:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": req.query})

    # 2. 调用 Azure AI Foundry 的 openai/v1/chat/completions
    url = f"{AZURE_OPENAI_ENDPOINT}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        # Foundry 通常支持 api-key 头；部分环境也接受 Bearer，这里两个都带上
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

    # 3. 模型返回内容解析为 JSON
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
            "disclaimer": "本回答不能替代医生面诊和正规医疗服务，仅供一般健康信息参考。如症状明显、持续或加重，请尽快前往正规医疗机构就诊或拨打当地急救电话。"
        }

    # 4. 安全兜底逻辑
    parsed = apply_safety_guard(parsed, user_query=req.query)

    # 5. 补齐缺失字段，适配 ConsultResponse
    parsed.setdefault("possible_diagnoses", [])
    parsed.setdefault("suggestions", [])
    parsed.setdefault("red_flags", [])
    parsed.setdefault("follow_up_questions", [])
    parsed.setdefault(
        "disclaimer",
        "本回答不能替代医生面诊和正规医疗服务，仅供一般健康信息参考。如症状明显、持续或加重，请尽快前往正规医疗机构就诊或拨打当地急救电话。"
    )

    if parsed.get("triage_level") not in ["emergency", "urgent", "non_urgent", "self_care", "unknown"]:
        parsed["triage_level"] = "unknown"

    return parsed
