from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import ContextRequest


class ContextStore:
    def __init__(self) -> None:
        self._store: dict[tuple[str, str], dict[str, Any]] = {}

    def upsert(self, request: ContextRequest) -> dict[str, Any]:
        key = (request.scope, request.context_id)
        current = self._store.get(key)

        if current is not None and request.version <= current["version"]:
            return {
                "accepted": False,
                "reason": "stale_version",
                "current_version": current["version"],
            }

        self._store[key] = {
            "scope": request.scope,
            "context_id": request.context_id,
            "version": request.version,
            "payload": request.payload,
            "delivered_at": request.delivered_at,
        }

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        return {
            "accepted": True,
            "ack_id": f"ack_{request.scope}_{request.context_id}_{request.version}",
            "stored_at": now,
        }

    def get(self, scope: str, context_id: str) -> dict[str, Any] | None:
        return self._store.get((scope, context_id))

    def context_counts(self) -> dict[str, int]:
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        for scope, _ in self._store.keys():
            if scope in counts:
                counts[scope] += 1
        return counts
