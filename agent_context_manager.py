"""
common/agent_context_manager.py — Redis-backed session context

Fixes vs original sketch:
  - Uses pipeline WATCH/MULTI/EXEC for atomic updates (no lost writes)
  - TTL on session keys (auto-cleanup after 24h)
  - Typed get/set helpers instead of raw dict access
  - Works in MOCK mode without real Redis (MemoryContextManager)
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

SESSION_TTL = 86400  # 24 hours


class AgentContextManager:
    """Redis-backed session context with optimistic locking."""

    def __init__(self, redis_client, session_id: str):
        self.r   = redis_client
        self.key = f"session:{session_id}:context"

    def get_context(self) -> dict:
        raw = self.r.get(self.key)
        return json.loads(raw) if raw else {}

    def set(self, field: str, value: Any) -> None:
        """Atomically set a single field in the context."""
        with self.r.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(self.key)
                    ctx = json.loads(pipe.get(self.key) or "{}")
                    ctx[field] = value
                    pipe.multi()
                    pipe.set(self.key, json.dumps(ctx), ex=SESSION_TTL)
                    pipe.execute()
                    break
                except Exception:
                    continue

    def append_history(self, entry: dict) -> None:
        """Atomically append to history list."""
        with self.r.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(self.key)
                    ctx = json.loads(pipe.get(self.key) or "{}")
                    ctx.setdefault("history", []).append(entry)
                    pipe.multi()
                    pipe.set(self.key, json.dumps(ctx), ex=SESSION_TTL)
                    pipe.execute()
                    break
                except Exception:
                    continue

    def get(self, field: str, default=None) -> Any:
        return self.get_context().get(field, default)


class MemoryContextManager:
    """
    In-memory drop-in for AgentContextManager.
    Use in MOCK mode and tests — no Redis required.
    """

    def __init__(self, session_id: str):
        self._ctx: dict = {}
        self.session_id = session_id

    def get_context(self) -> dict:
        return dict(self._ctx)

    def set(self, field: str, value: Any) -> None:
        self._ctx[field] = value

    def append_history(self, entry: dict) -> None:
        self._ctx.setdefault("history", []).append(entry)

    def get(self, field: str, default=None) -> Any:
        return self._ctx.get(field, default)
