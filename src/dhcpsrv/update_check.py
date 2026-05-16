"""
Auto-update check.

On startup, ask GitHub for the latest release tag. If it's newer than the
local `__version__`, ask the user whether to open the download page in a
browser. Silent on any error (offline, rate-limit, etc.)."""

from __future__ import annotations
import json
import urllib.request
import webbrowser

from rich.console import Console
from rich.prompt  import Confirm

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


def check_for_update(console: Console) -> None:
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={
            "Accept":     "application/vnd.github+json",
            "User-Agent": f"dhcpsrv/{__version__}",
        })
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        latest = (data.get("tag_name") or "").strip()
        page   = data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"

        if _parse_version(latest) > _parse_version(__version__):
            console.rule("[bold yellow]Update available")
            console.print(f"Current: [dim]v{__version__}[/]    Latest: [bold green]{latest}[/]")
            try:
                if Confirm.ask("Open the download page in your browser?", default=True):
                    webbrowser.open(page)
            except (EOFError, KeyboardInterrupt):
                pass
            console.print()
    except Exception:
        # Offline / API error — silent on purpose.
        pass
