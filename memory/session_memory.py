"""Session-scoped conversation memory (Redis with in-memory fallback)."""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# In-memory fallback when Redis is unavailable
_local_store: Dict[str, Dict] = {}


class SessionMemory:
    def __init__(self, ttl: int = 86400):
        self.ttl = ttl
        self._redis = None
        self._redis_ok = True

    async def _get_redis(self):
        if not self._redis_ok:
            return None
        try:
            if self._redis is None:
                from config.redis_config import get_redis
                self._redis = await get_redis()
            return self._redis
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory session store: {e}")
            self._redis_ok = False
            return None

    def _local(self, session_id: str) -> Dict:
        if session_id not in _local_store:
            _local_store[session_id] = {"messages": [], "state": {}}
        return _local_store[session_id]

    async def append_message(self, session_id: str, role: str, content: str, language: str = "en"):
        message = {
            "role": role,
            "content": content,
            "language": language,
            "timestamp": datetime.utcnow().isoformat(),
        }
        redis = await self._get_redis()
        if redis:
            try:
                key = f"session:{session_id}:messages"
                await redis.lpush(key, json.dumps(message))
                await redis.expire(key, self.ttl)
                return
            except Exception as e:
                logger.warning(f"Redis append failed: {e}")
                self._redis_ok = False

        store = self._local(session_id)
        store["messages"].append(message)
        if len(store["messages"]) > 40:
            store["messages"] = store["messages"][-40:]

    async def get_messages(self, session_id: str, limit: int = 10) -> List[Dict]:
        redis = await self._get_redis()
        if redis:
            try:
                key = f"session:{session_id}:messages"
                raw = await redis.lrange(key, 0, limit - 1)
                messages = []
                for item in reversed(raw):
                    try:
                        messages.append(json.loads(item))
                    except json.JSONDecodeError:
                        continue
                return messages
            except Exception as e:
                logger.warning(f"Redis read failed: {e}")
                self._redis_ok = False

        return self._local(session_id)["messages"][-limit:]

    async def set_state(self, session_id: str, state: Dict):
        redis = await self._get_redis()
        if redis:
            try:
                key = f"session:{session_id}:state"
                await redis.set(key, json.dumps(state), ex=self.ttl)
                return
            except Exception as e:
                logger.warning(f"Redis state write failed: {e}")
                self._redis_ok = False

        self._local(session_id)["state"] = state

    async def get_state(self, session_id: str) -> Optional[Dict]:
        redis = await self._get_redis()
        if redis:
            try:
                key = f"session:{session_id}:state"
                data = await redis.get(key)
                return json.loads(data) if data else None
            except Exception as e:
                logger.warning(f"Redis state read failed: {e}")
                self._redis_ok = False

        return self._local(session_id).get("state") or None

    async def merge_pending_booking(self, session_id: str, updates: Dict) -> Dict:
        state = await self.get_state(session_id) or {}
        pending = state.get("pending_booking", {})
        pending.update({k: v for k, v in updates.items() if v})
        state["pending_booking"] = pending
        await self.set_state(session_id, state)
        return pending

    async def merge_pending_reschedule(self, session_id: str, updates: Dict) -> Dict:
        state = await self.get_state(session_id) or {}
        pending = state.get("pending_reschedule", {})
        pending.update({k: v for k, v in updates.items() if v})
        state["pending_reschedule"] = pending
        await self.set_state(session_id, state)
        return pending

    async def clear_flow_state(self, session_id: str):
        """Clear in-progress booking/reschedule state (keeps last phone/appointment refs)."""
        state = await self.get_state(session_id) or {}
        state.pop("pending_booking", None)
        state.pop("pending_reschedule", None)
        await self.set_state(session_id, state)
