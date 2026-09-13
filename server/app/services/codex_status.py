"""Read safe Codex CLI account status through the app-server protocol."""

import asyncio
import json
import subprocess
from typing import Any


class CodexStatusError(RuntimeError):
    pass


def _write(process: subprocess.Popen[str], value: dict[str, Any]) -> None:
    if process.stdin is None:
        raise CodexStatusError("Codex stdin is unavailable")
    process.stdin.write(json.dumps(value) + "\n")
    process.stdin.flush()


def _response(
    process: subprocess.Popen[str], request_id: int,
) -> dict[str, Any]:
    if process.stdout is None:
        raise CodexStatusError("Codex stdout is unavailable")
    while line := process.stdout.readline():
        value = json.loads(line)
        if value.get("id") == request_id:
            if "error" in value:
                raise CodexStatusError("Codex status request failed")
            return value.get("result", {})
    raise CodexStatusError("Codex status stream ended")


class CodexStatusService:
    def __init__(self, executable: str = "codex", timeout_seconds: float = 10) -> None:
        self._executable = executable
        self._timeout_seconds = timeout_seconds

    async def read(self) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._read_sync),
                timeout=self._timeout_seconds,
            )
        except FileNotFoundError:
            return self._empty(False, "cli_not_found")
        except (
            CodexStatusError, OSError, asyncio.TimeoutError,
            json.JSONDecodeError,
        ):
            return self._empty(True, "status_unavailable")
        except Exception:
            return self._empty(True, "status_unavailable")

    def _read_sync(self) -> dict[str, Any]:
        process = subprocess.Popen(
            (self._executable, "app-server", "--stdio"),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
        )
        try:
            _write(process, {
                "method": "initialize", "id": 0,
                "params": {"clientInfo": {
                    "name": "personal-agent-workspace",
                    "title": "Personal Agent Workspace", "version": "0.1.0",
                }},
            })
            _response(process, 0)
            _write(process, {"method": "initialized", "params": {}})
            _write(process, {
                "method": "account/read", "id": 1,
                "params": {"refreshToken": False},
            })
            account = _response(process, 1)
            _write(process, {"method": "account/rateLimits/read", "id": 2})
            limits = _response(process, 2)
            return self._normalize(account, limits)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()

    @staticmethod
    def _normalize(account: dict[str, Any], limits: dict[str, Any]) -> dict[str, Any]:
        identity = account.get("account")
        snapshot = (limits.get("rateLimitsByLimitId") or {}).get("codex")
        snapshot = snapshot or limits.get("rateLimits") or {}
        windows = []
        for name in ("primary", "secondary"):
            window = snapshot.get(name)
            if isinstance(window, dict):
                windows.append({
                    "name": name,
                    "used_percent": window.get("usedPercent", 0),
                    "window_minutes": window.get("windowDurationMins"),
                    "resets_at": window.get("resetsAt"),
                })
        return {
            "installed": True, "authenticated": identity is not None,
            "auth_mode": identity.get("type") if isinstance(identity, dict) else None,
            "plan_type": snapshot.get("planType"), "windows": windows,
            "error": None if identity is not None else "not_authenticated",
        }

    @staticmethod
    def _empty(installed: bool, error: str) -> dict[str, Any]:
        return {
            "installed": installed, "authenticated": False,
            "auth_mode": None, "plan_type": None, "windows": [], "error": error,
        }


