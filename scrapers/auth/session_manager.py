"""
Browser session manager — persists Playwright storage state (cookies +
localStorage) to disk so spiders survive restarts without re-logging in.

Storage state is stored as JSON at the path configured in settings.
The file is gitignored and never leaves the local machine.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from loguru import logger


class SessionManager:
    """
    Persists and restores Playwright browser storage state.

    Playwright's storage_state() returns a dict with:
      {
        "cookies": [ {...}, ... ],
        "origins": [ {"origin": "...", "localStorage": [...]} ]
      }

    This is the complete authenticated browser state — more complete than
    saving cookies alone because it also captures localStorage tokens.
    """

    def __init__(self, session_file: str) -> None:
        self.path = Path(session_file)

    # ─── Persistence ─────────────────────────────────────────────────────────

    def save(self, storage_state: dict[str, Any]) -> None:
        """Persist storage state to disk with a timestamp."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": time.time(),
            "storage_state": storage_state,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Session saved → {}", self.path)

    def load(self) -> dict[str, Any] | None:
        """Load storage state from disk. Returns None if not found or corrupted."""
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            state = payload.get("storage_state")
            if not state or not state.get("cookies"):
                logger.debug("Session file exists but has no cookies.")
                return None
            return state
        except Exception as exc:
            logger.warning("Could not read session file: {}", exc)
            return None

    def clear(self) -> None:
        """Delete saved session — forces re-authentication on next run."""
        if self.path.exists():
            self.path.unlink()
            logger.info("Session cleared — will re-authenticate on next run.")

    def exists(self) -> bool:
        return self.path.exists() and self.load() is not None

    def age_hours(self) -> float | None:
        """Return session age in hours, or None if no session saved."""
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            saved_at = payload.get("saved_at", 0)
            return (time.time() - saved_at) / 3600
        except Exception:
            return None
