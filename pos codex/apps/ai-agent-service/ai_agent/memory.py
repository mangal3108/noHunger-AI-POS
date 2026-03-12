import json
from copy import deepcopy
from typing import Any

try:
    from redis.asyncio import Redis
except Exception:  # pragma: no cover
    Redis = None  # type: ignore


DEFAULT_SESSION_STATE: dict[str, Any] = {
    "preferences": {},
    "selected_restaurant": None,
    "delivery_address": None,
    "payment_method": None,
    "order_history": [],
    "cart": [],
    "last_order_id": None,
    "conversation_history": [],
    "conversation_memory": {
        "name": None,
        "dietary": None,
        "spice_preference": None,
        "budget_inr": None,
        "preferred_payment_method": None,
        "last_requested_food_type": None,
    },
    "pending_slot": None,
}


def new_session_state() -> dict[str, Any]:
    return deepcopy(DEFAULT_SESSION_STATE)


class SessionMemory:
    def __init__(self, redis_url: str) -> None:
        # Keep Redis optional and fail fast when the server is unavailable.
        if redis_url:
            redis_url = str(redis_url).strip('"').strip("'")
        
        # Validate URL scheme to prevent common misconfigurations (especially on Render)
        is_valid_redis = False
        if redis_url and any(redis_url.startswith(s) for s in ["redis://", "rediss://", "unix://"]):
            is_valid_redis = True
            
        self._redis = (
            Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
                retry_on_timeout=False,
            )
            if Redis and is_valid_redis
            else None
        )
        self._local_store: dict[str, dict[str, Any]] = {}

    async def get(self, session_id: str) -> dict[str, Any]:
        if self._redis:
            try:
                value = await self._redis.get(self._key(session_id))
                if value:
                    return json.loads(value)
            except Exception:
                self._redis = None
        return self._local_store.get(session_id, new_session_state())

    async def set(self, session_id: str, state: dict[str, Any]) -> None:
        if self._redis:
            try:
                await self._redis.set(self._key(session_id), json.dumps(state))
            except Exception:
                self._redis = None
                self._local_store[session_id] = state
                return
        else:
            self._local_store[session_id] = state

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session:{session_id}"
