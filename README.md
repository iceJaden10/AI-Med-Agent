# 🩺 AI Medical Triage System

An end-to-end **multimodal medical consultation and triage system** that integrates **large language models (LLMs)** with **vision-language models** to analyze user-reported symptoms and medical images. The system delivers structured medical reasoning, safety-aware guidance, and preliminary triage recommendations in real-world web scenarios.

---

## 📌 Project Overview

In real medical consultations, patients often describe symptoms using **unstructured text** and **ambiguous images**. Traditional text-only systems may overlook critical visual cues and thus produce incomplete or unsafe guidance.

This project proposes a **multimodal medical triage pipeline** that combines **visual evidence** with **textual symptom descriptions** to improve:

- Triage accuracy  
- Medical reasoning specificity  
- Safety awareness  
- Consistency between visual evidence and generated advice  

The system is designed to be **deployable, interpretable, and safety-oriented**, rather than a proof-of-concept demo.

---

## ✨ Key Features

- Text + medical image input (multimodal consultation)
- Automated triage level classification
- Structured medical summaries with reasoning
- Explicit safety alerts and escalation guidance
- Session-based multi-turn conversations
- Fully deployed web system (frontend + backend)

---

## 🧠 System Architecture

```text
User
 │
 │  Text / Medical Image
 ▼
Frontend (React + TypeScript)
 │
 ▼
FastAPI Backend
 │
 ├─ Vision Model (Qwen-VL)
 │   └─ Medical image caption / visual findings
 │
 ├─ Symptom Structuring & Multimodal Fusion
 │
 ├─ LLM Medical Reasoning (Qwen3-max / Azure OpenAI)
 │
 ▼
Triage Decision + Safety-Aware Medical Advice
```

## 🧩 Tech Stack

### Frontend
- **Framework**: React  
- **Language**: TypeScript  
- **Build Tool**: Vite  
- **Styling**: Tailwind CSS  
- **Networking**: Axios / Fetch  
- **UI Pattern**: Session-based chat interface  

### Backend
- **Framework**: FastAPI  
- **Language**: Python 3.10+  
- **ORM**: SQLAlchemy  
- **Database**: SQLite (default) / MySQL (Docker)  
- **Session Management**: Database-based (Redis-ready)  
- **Server**: Gunicorn + Uvicorn  

### AI & Models
- **Qwen3-max**
  - Medical reasoning  
  - Symptom interpretation  
  - Triage decision making  

- **Qwen-VL**
  - Medical image understanding  
  - Visual feature extraction and captioning  

- **LLM Routing**
  - Supports Azure OpenAI and other API-based models  
  - Prompt-based, safety-constrained medical reasoning  

### Deployment & Infrastructure
- **Cloud**: Alibaba Cloud ECS (CentOS)  
- **Reverse Proxy**: Nginx  
- **Protocol**: HTTPS with custom domain  
- **Process Management**: systemd  
- **Containerization**: Docker / Docker Compose (optional)  

---

## 📊 Triage Level Design

| Level | Description | Typical Scenarios |
|------|------------|------------------|
| 🔴 Emergency | Immediate medical attention required | Severe bleeding, breathing difficulty |
| 🟠 Clinic Visit | Outpatient visit recommended | Infection-prone wounds, worsening symptoms |
| 🟢 Self-care | Home care sufficient | Minor abrasions, mild symptoms |

---

## 🔬 Project Highlights

### Multimodal Comparison Study
Qualitative comparison between **text-only** and **text + image** inputs using real interactive cases from the deployed platform.

### Explainable Medical Reasoning
Model outputs explicitly reference observable visual features such as redness, bleeding, swelling, or wound depth.

### Safety-First Design Philosophy
Conservative triage decisions, non-diagnostic framing, and clearly defined escalation boundaries.

### Production-Oriented Engineering
Complete frontend–backend integration, session persistence, cloud deployment, and domain access.

---

## 🧪 Example Case Study

**Case: Superficial Knee Abrasion**

- **Input**: Knee image + “what happened to my leg”
- **Visual Findings**:
  - Superficial tissue damage  
  - Mild active bleeding  
  - Local redness  
- **Triage Output**: 🟠 Clinic Visit  
- **Medical Advice**:
  - Clean and disinfect the wound  
  - Monitor for signs of infection  
  - Verify tetanus vaccination status  

---

## 🚀 Local Setup

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```