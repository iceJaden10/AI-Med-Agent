# session_store.py
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from db import SessionLocal
from models import ConversationSession

# Redis 是可选的，将来要用再安装：pip install redis
try:
    import redis  # type: ignore
except ImportError:
    redis = None


class SQLiteSessionStore:
    """
    SQLite 会话存储：
    - history_json 里统一存：{"summary": "...", "messages": [...], "updated_at": "..."}
    - 兼容旧数据（直接存的是 list）
    - 带 TTL 自动过期
    """
    DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds

    # ---------- 内部工具 ----------

    def _get_db(self) -> Session:
        return SessionLocal()

    def _is_expired(self, updated_at: datetime, ttl_seconds: int) -> bool:
        return datetime.utcnow() > updated_at + timedelta(seconds=ttl_seconds)

    def _decode_history_json(self, history_json: str) -> Dict[str, Any]:
        """
        统一解析为：
        {
          "summary": str,
          "messages": List[dict],
          "updated_at": str | None
        }
        """
        if not history_json:
            return {"summary": "", "messages": [], "updated_at": None}

        try:
            data = json.loads(history_json)
        except json.JSONDecodeError:
            return {"summary": "", "messages": [], "updated_at": None}

        # 旧格式：直接是 list
        if isinstance(data, list):
            return {"summary": "", "messages": data, "updated_at": None}

        # 新格式：dict
        if not isinstance(data, dict):
            return {"summary": "", "messages": [], "updated_at": None}

        summary = data.get("summary", "") or ""
        messages = data.get("messages", []) or []
        if not isinstance(messages, list):
            messages = []

        updated_at = data.get("updated_at")  # 可能不存在，兼容旧数据

        return {
            "summary": summary,
            "messages": messages,
            "updated_at": updated_at,
        }

    def _encode_history_json(
        self,
        summary: str,
        messages: List[Dict[str, str]],
        updated_at: Optional[datetime] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "summary": summary or "",
            "messages": messages or [],
        }
        if updated_at is not None:
            payload["updated_at"] = updated_at.isoformat()
        return json.dumps(payload, ensure_ascii=False)

    # ---------- 对外接口：session 级别 ----------

    def get_session(self, user_id: str) -> Dict[str, Any]:
        """
        返回：
        {
          "summary": str,      # 全局会话摘要（可为空字符串）
          "messages": [ ... ], # 最近若干轮对话
          "updated_at": str | None
        }
        """
        db = self._get_db()
        try:
            row = db.query(ConversationSession).filter_by(user_id=user_id).first()
            if not row:
                return {"summary": "", "messages": [], "updated_at": None}

            ttl = row.ttl_seconds or self.ttl_seconds
            if self._is_expired(row.updated_at, ttl):
                db.delete(row)
                db.commit()
                return {"summary": "", "messages": [], "updated_at": None}

            decoded = self._decode_history_json(row.history_json)

            # 如果 JSON 里没有 updated_at 字段，用行里的 updated_at 补上
            if not decoded.get("updated_at"):
                decoded["updated_at"] = row.updated_at.isoformat()

            return decoded
        finally:
            db.close()

    def save_session(self, user_id: str, summary: str, messages: List[Dict[str, str]]) -> None:
        """
        保存当前会话（摘要 + 消息）。
        """
        db = self._get_db()
        try:
            row = db.query(ConversationSession).filter_by(user_id=user_id).first()
            now = datetime.utcnow()
            encoded = self._encode_history_json(summary, messages, now)

            if not row:
                row = ConversationSession(
                    user_id=user_id,
                    history_json=encoded,
                    updated_at=now,
                    ttl_seconds=self.ttl_seconds,
                )
                db.add(row)
            else:
                row.history_json = encoded
                row.updated_at = now

            db.commit()
        finally:
            db.close()

    def reset_session(self, user_id: str) -> None:
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
            decoded = self._decode_history_json(row.history_json)
            messages = decoded.get("messages", [])

            return {
                "exists": True,
                "message_count": len(messages),
                "last_updated": row.updated_at.isoformat(),
                "expired": expired,
                "ttl_seconds": ttl,
            }
        finally:
            db.close()

    # ---------- 兼容旧接口（不带摘要） ----------

    def get_history(self, user_id: str) -> List[Dict[str, str]]:
        return self.get_session(user_id).get("messages", [])

    def save_history(self, user_id: str, history: List[Dict[str, str]]) -> None:
        session = self.get_session(user_id)
        summary = session.get("summary", "")
        self.save_session(user_id, summary, history)


# =================== Redis 版本 ===================

class RedisSessionStore:
    """
    Redis 会话存储（为未来云端扩容准备）：
    - key: session:{user_id}
    - value: {"summary": "...", "messages": [...], "updated_at": "..."}
    - 利用 Redis 自身的 TTL 过期
    """
    DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h

    def __init__(self, url: str = "redis://localhost:6379/0", ttl_seconds: int = DEFAULT_TTL_SECONDS):
        if redis is None:
            raise ImportError(
                "RedisSessionStore 需要安装 redis 库，请先执行：pip install redis"
            )
        self.ttl_seconds = ttl_seconds
        self.client = redis.Redis.from_url(url)

    def _key(self, user_id: str) -> str:
        return f"session:{user_id}"

    def get_session(self, user_id: str) -> Dict[str, Any]:
        data = self.client.get(self._key(user_id))
        if not data:
            return {"summary": "", "messages": [], "updated_at": None}

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return {"summary": "", "messages": [], "updated_at": None}

        # 兼容 list 格式
        if isinstance(payload, list):
            return {"summary": "", "messages": payload, "updated_at": None}

        if not isinstance(payload, dict):
            return {"summary": "", "messages": [], "updated_at": None}

        summary = payload.get("summary", "") or ""
        messages = payload.get("messages", []) or []
        if not isinstance(messages, list):
            messages = []

        updated_at = payload.get("updated_at")

        return {
            "summary": summary,
            "messages": messages,
            "updated_at": updated_at,
        }

    def save_session(self, user_id: str, summary: str, messages: List[Dict[str, str]]) -> None:
        payload = {
            "summary": summary or "",
            "messages": messages or [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.client.set(
            self._key(user_id),
            json.dumps(payload, ensure_ascii=False),
            ex=self.ttl_seconds,
        )

    def reset_session(self, user_id: str) -> None:
        self.client.delete(self._key(user_id))

    def get_status(self, user_id: str) -> Dict[str, Any]:
        key = self._key(user_id)
        data = self.client.get(key)
        if not data:
            return {
                "exists": False,
                "message_count": 0,
                "last_updated": None,
                "expired": False,
                "ttl_seconds": None,
            }

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            payload = {}

        messages = payload.get("messages", []) if isinstance(payload, dict) else []
        if not isinstance(messages, list):
            messages = []

        ttl = self.client.ttl(key)
        expired = ttl is not None and ttl <= 0

        return {
            "exists": True,
            "message_count": len(messages),
            "last_updated": payload.get("updated_at"),
            "expired": expired,
            "ttl_seconds": ttl if ttl and ttl > 0 else self.DEFAULT_TTL_SECONDS,
        }

    # 兼容旧接口
    def get_history(self, user_id: str) -> List[Dict[str, str]]:
        return self.get_session(user_id).get("messages", [])

    def save_history(self, user_id: str, history: List[Dict[str, str]]) -> None:
        session = self.get_session(user_id)
        summary = session.get("summary", "")
        self.save_session(user_id, summary, history)
