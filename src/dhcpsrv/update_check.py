"""
Auto-update check.

On startup, ask GitHub for the latest release tag. If it's newer than the
local `__version__`, return the tag string so the caller can show a quiet
hint in the header. Silent on any error (offline, rate-limit, etc.).
"""

from __future__ import annotations
import json
import urllib.request

from . import __version__, GITHUB_REPO


def _parse_version(s: str) -> tuple[int, int, int]:
    try:
        s = (s or "").strip().lstrip("v")
        parts = [int(x) for x in s.split(".")[:3]]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts)  # type: ignore[return-value]
    except Exception:
        return (0, 0, 0)


def check_for_update() -> str | None:
    """Return the latest release tag (e.g. 'v1.2.0') if it is newer than the
    currently running version. Returns None when up to date, offline, or on
    any error — the caller decides how (or whether) to render the hint."""
    try:
        url = f"https://git.engelgardt23.ru/api/v1/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={
            "User-Agent": f"dhcpsrv/{__version__}",
        })
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        latest = (data.get("tag_name") or "").strip()
        if latest and _parse_version(latest) > _parse_version(__version__):
            return latest
    except Exception:
        pass
    return None
