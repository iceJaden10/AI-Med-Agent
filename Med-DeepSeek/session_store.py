# session_store.py
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from db import SessionLocal
from models import ConversationSession


class SQLiteSessionStore:
    """简单的 SQLite 会话存储，带 TTL 机制"""
    DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds

    def _get_db(self) -> Session:
        return SessionLocal()

    def _is_expired(self, updated_at: datetime, ttl_seconds: int) -> bool:
        return datetime.utcnow() > updated_at + timedelta(seconds=ttl_seconds)

    def get_history(self, user_id: str) -> List[Dict[str, str]]:
        """
        返回该 user_id 的历史消息列表：
        [
          {"role": "user", "content": "..."},
          {"role": "assistant", "content": "..."},
          ...
        ]
        """
        db = self._get_db()
        try:
            row = db.query(ConversationSession).filter_by(user_id=user_id).first()
            if not row:
                return []

            ttl = row.ttl_seconds or self.ttl_seconds
            if self._is_expired(row.updated_at, ttl):
                # 过期视为无历史，可以顺便删除
                db.delete(row)
                db.commit()
                return []

            return json.loads(row.history_json or "[]")
        finally:
            db.close()

    def save_history(self, user_id: str, history: List[Dict[str, str]]) -> None:
        """
        存/更新会话历史，并刷新 updated_at
        """
        db = self._get_db()
        try:
            row = db.query(ConversationSession).filter_by(user_id=user_id).first()
            now = datetime.utcnow()

            if not row:
                row = ConversationSession(
                    user_id=user_id,
                    history_json=json.dumps(history, ensure_ascii=False),
                    updated_at=now,
                    ttl_seconds=self.ttl_seconds,
                )
                db.add(row)
            else:
                row.history_json = json.dumps(history, ensure_ascii=False)
                row.updated_at = now

            db.commit()
        finally:
            db.close()

    def reset_session(self, user_id: str) -> None:
        """
        删除该 user_id 的历史记录
        """
        db = self._get_db()
        try:
            row = db.query(ConversationSession).filter_by(user_id=user_id).first()
            if row:
                db.delete(row)
                db.commit()
        finally:
            db.close()

    def get_status(self, user_id: str) -> Dict[str, Any]:
        """
        返回会话状态：
        {
          "exists": bool,
          "message_count": int,
          "last_updated": str | None,
          "expired": bool,
          "ttl_seconds": int | None
        }
        """
        db = self._get_db()
        try:
            row = db.query(ConversationSession).filter_by(user_id=user_id).first()
            if not row:
                return {
                    "exists": False,
                    "message_count": 0,
                    "last_updated": None,
                    "expired": False,
                    "ttl_seconds": None,
                }

            ttl = row.ttl_seconds or self.ttl_seconds
            expired = self._is_expired(row.updated_at, ttl)
            history = json.loads(row.history_json or "[]")

            return {
                "exists": True,
                "message_count": len(history),
                "last_updated": row.updated_at.isoformat(),
                "expired": expired,
                "ttl_seconds": ttl,
            }
        finally:
            db.close()
