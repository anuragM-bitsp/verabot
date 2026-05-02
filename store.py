"""
In-memory context store with versioned, scoped storage.
Supports: merchant, customer, trigger, session scopes.
"""

import threading
from typing import Any, Optional


class ContextStore:
    """
    Thread-safe versioned key-value store.
    Keys: (scope, context_id) → {version, payload}
    Higher version replaces atomically; same version is a no-op.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._store: dict[tuple[str, str], dict] = {}
        self._sessions: dict[str, dict] = {}

    def put(self, scope: str, context_id: str, version: int, payload: dict) -> bool:
        """
        Store context. Returns True if stored, False if no-op (same or lower version).
        """
        key = (scope, context_id)
        with self._lock:
            existing = self._store.get(key)
            if existing and existing["version"] >= version:
                return False
            self._store[key] = {"version": version, "payload": payload}
            return True

    def get(self, scope: str, context_id: str) -> Optional[dict]:
        """Return payload dict or None."""
        key = (scope, context_id)
        with self._lock:
            entry = self._store.get(key)
            return entry["payload"] if entry else None

    def put_session(self, session_id: str, data: dict):
        with self._lock:
            self._sessions[session_id] = data

    def get_session(self, session_id: str) -> Optional[dict]:
        with self._lock:
            return self._sessions.get(session_id)

    def all_by_scope(self, scope: str) -> dict[str, dict]:
        with self._lock:
            return {
                cid: entry["payload"]
                for (sc, cid), entry in self._store.items()
                if sc == scope
            }

    def stats(self) -> dict:
        with self._lock:
            scope_counts: dict[str, int] = {}
            for (scope, _) in self._store:
                scope_counts[scope] = scope_counts.get(scope, 0) + 1
            return {
                "total_entries": len(self._store),
                "sessions": len(self._sessions),
                "by_scope": scope_counts,
            }
