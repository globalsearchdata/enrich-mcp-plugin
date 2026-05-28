"""
Simple in-memory rate limiter with file persistence.

Per IP:
  - Max TOTAL requests: per_ip_limit (e.g. 10)
  - Max requests per window: per_ip_window_limit (e.g. 5) within per_ip_window (e.g. 60s)

Global:
  - Max TOTAL requests across all IPs: global_limit (e.g. 10000)

State is persisted to a JSON file so limits survive server restarts.
"""

import json
import logging
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)


class RateLimiter:
    def __init__(
        self,
        state_file: Path,
        per_ip_limit: int = 10,
        per_ip_window: int = 60,
        per_ip_window_limit: int = 5,
        global_limit: int = 10000,
    ):
        self._state_file = state_file
        self._per_ip_limit = per_ip_limit
        self._per_ip_window = per_ip_window          # seconds
        self._per_ip_window_limit = per_ip_window_limit
        self._global_limit = global_limit

        self._lock = threading.Lock()
        self._state = self._load()

    # ── persistence ──────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                return data
            except Exception:
                log.exception("Failed to load rate state, starting fresh")
        return {"ips": {}, "global_total": 0}

    def _save(self):
        try:
            self._state_file.write_text(json.dumps(self._state, indent=2))
        except Exception:
            log.exception("Failed to persist rate state")

    # ── check ────────────────────────────────────────────────────────────

    def check(self, ip: str) -> tuple[bool, str]:
        """Return (allowed, reason).  allowed=True means the request can proceed."""
        now = time.time()
        window_start = now - self._per_ip_window

        with self._lock:
            state = self._state
            ip_data = state["ips"].setdefault(ip, {"total": 0, "window_ts": []})

            # prune old window entries
            ip_data["window_ts"] = [t for t in ip_data["window_ts"] if t > window_start]

            # ── check global limit ──
            if state["global_total"] >= self._global_limit:
                self._save()
                return False, "global limit reached"

            # ── check per-IP total limit ──
            if ip_data["total"] >= self._per_ip_limit:
                self._save()
                return False, f"IP total limit reached ({self._per_ip_limit})"

            # ── check per-IP window limit ──
            if len(ip_data["window_ts"]) >= self._per_ip_window_limit:
                self._save()
                return False, (
                    f"IP rate limit exceeded ({self._per_ip_window_limit} per "
                    f"{self._per_ip_window}s)"
                )

            # ── ALLOW ──
            ip_data["total"] += 1
            ip_data["window_ts"].append(now)
            state["global_total"] += 1
            self._save()
            return True, "ok"

    # ── stats ────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        with self._lock:
            return {
                "global_total": self._state["global_total"],
                "global_limit": self._global_limit,
                "ips": {
                    ip: {
                        "total": d["total"],
                        "ip_limit": self._per_ip_limit,
                        "window_count": len(d["window_ts"]),
                        "window_limit": self._per_ip_window_limit,
                        "window_seconds": self._per_ip_window,
                    }
                    for ip, d in self._state["ips"].items()
                },
            }
