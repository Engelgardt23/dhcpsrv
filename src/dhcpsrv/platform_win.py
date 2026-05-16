"""
Windows-specific bits: VT (ANSI) processing in the console, UAC self-elevation.
"""

from __future__ import annotations
import ctypes
import os
import sys


def enable_vt() -> None:
    """Enable virtual-terminal processing on the Windows console so that ESC
    escape sequences from raw stdout writes are interpreted as colours / clear
    instead of being printed as literal characters.

    Rich enables this for its own writes; we still call it so direct
    `sys.stdout.write("\\x1b[...")` works (used to clear the scrollback when
    the alt screen starts)."""
    if os.name != "nt":
        return
    try:
        k = ctypes.windll.kernel32
        STD_OUT, STD_ERR = -11, -12
        ENABLE_VT = 0x0004
        for std in (STD_OUT, STD_ERR):
            h = k.GetStdHandle(std)
            mode = ctypes.c_ulong()
            if k.GetConsoleMode(h, ctypes.byref(mode)):
                k.SetConsoleMode(h, mode.value | ENABLE_VT)
    except Exception:
        pass


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def require_admin() -> None:
    """If we're not running elevated, relaunch ourselves through UAC and exit.

    Works both for the PyInstaller bundle (`sys.executable` is the exe itself)
    and for a plain `python src/dhcpsrv/__main__.py` run."""
    if is_admin():
        return
    args = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1)
    sys.exit(0)
