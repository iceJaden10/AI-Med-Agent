from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Integer, Float

from db import Base


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    user_id = Column(String, primary_key=True, index=True)
    history_json = Column(Text, nullable=False, default="[]")
    updated_at = Column(DateTime, default=datetime.utcnow)
    ttl_seconds = Column(Integer, default=86400)  # 默认 24h


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(String, primary_key=True, index=True)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    chronic_diseases_json = Column(Text, nullable=False, default="[]")
    allergies_json = Column(Text, nullable=False, default="[]")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
