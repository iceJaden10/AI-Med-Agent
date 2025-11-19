# models.py
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Integer

from db import Base


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    user_id = Column(String, primary_key=True, index=True)
    history_json = Column(Text, nullable=False, default="[]")
    updated_at = Column(DateTime, default=datetime.utcnow)
    ttl_seconds = Column(Integer, default=86400)  # 默认 24h
