# 🏥 智能医疗问诊系统 · 后端（Med-DeepSeek Backend）

后端负责对接医疗大模型、管理问诊上下文、输出结构化医疗问诊结果，并为前端提供 REST API 接口。

---

## 1. 功能介绍

### ✔ 医疗问诊接口（/api/consult）
- 输入用户自然语言症状
- 调用医疗模型生成问诊回答
- 返回结构化内容，包括：
  - `answer`（问诊回复）
  - `risk_level`（风险等级：绿/黄/红）
  - `red_flags`（高危症状提示）
  - `possible_diagnosis`（可能诊断列表）
  - `follow_up_questions`（下一步追问）

### ✔ 多轮对话上下文（SessionStore）
- 按 `user_id` 存储问诊历史
- 支持自动摘要（防止上下文过长）
- 当前提供内存版 & SQLite 储存

### ✔ 系统医疗 Prompt（system_prompt_medical_zh.txt）
- 对模型进行医疗问诊安全约束
- 控制输出格式、风险分级、追问逻辑

### ✔ 简易数据库支持（sessions.db）
- 用于本地存储对话上下文（可替换成 Redis）

---

## 2. 技术栈

| 模块 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| Web Server | Uvicorn |
| 模型推理 | DeepSeek / Huatuo（本地或远端） |
| 数据处理 | Pydantic |
| 会话存储 | SQLite（当前）、可切换 Redis |
| 环境变量 | python-dotenv |
| 依赖管理 | requirements.txt |

---

## 3. 项目结构
```
backend/
├── main.py # FastAPI 入口，定义 /api/consult
├── models.py # 请求和响应的数据模型
├── session_store.py # 会话上下文存储（内存/SQLite）
├── db.py # SQLite 存储工具
├── sessions.db # 本地会话数据
├── system_prompt_medical_zh.txt # 医疗系统 Prompt
├── requirements.txt # 依赖列表
├── .env # 环境变量
└── backlog.txt # 后端任务 backlog
```

---

## 4. 待办内容（Backlog）

- [ ] 接入 Redis（替代 SQLite 存储 sessions）
- [ ] 增加自动摘要模块（LLM summary）
- [ ] 引入云端推理（Azure / DeepSeek API）
- [ ] 增强风险分级 rule-based 校验
- [ ] 增加症状 → 疾病知识库（Rule + LLM Hybrid）
- [ ] 增加前端所需的统一错误处理
- [ ] 单元测试（pytest）
- [ ] 进一步模块化（拆分成 `api/`, `core/`, `services/`）

---

