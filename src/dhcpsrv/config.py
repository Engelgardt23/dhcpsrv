"""
config.ini handling next to the executable.

On first run the file does not exist — we ask the user which language to use
and write the answer alongside the exe. On every subsequent run we just read
it. The .ini has a leading bilingual comment explaining how to change values
by editing the file directly.
"""

from __future__ import annotations
import configparser
import sys
from pathlib import Path


SUPPORTED_LANGS = ("en", "ru")
DEFAULT_LANG    = "en"

CONFIG_HEADER = """\
# ---------------------------------------------------------------------------
# dhcpsrv configuration
#
# To change the interface language, edit the 'language' value below.
# Valid values: en, ru
#
# Чтобы сменить язык интерфейса, измените значение 'language' ниже.
# Допустимые значения: en, ru
# ---------------------------------------------------------------------------

"""


def app_dir() -> Path:
    """Directory holding the running executable (or source folder when run via python)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def config_path() -> Path:
    return app_dir() / "config.ini"


def _ask_language() -> str:
    """First-run prompt. Stdin is always available in console apps, no Rich here
    yet (we run before the main console is set up)."""
    print()
    print("Select language / Выберите язык:")
    print("  1) English")
    print("  2) Русский")
    while True:
        try:
            choice = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            return DEFAULT_LANG
        if choice == "1":
            return "en"
        if choice == "2":
            return "ru"
        print("Please enter 1 or 2 / Введите 1 или 2")


def _write_config(lang: str) -> None:
    path = config_path()
    cp = configparser.ConfigParser()
    cp["General"] = {"language": lang}
    with path.open("w", encoding="utf-8") as f:
        f.write(CONFIG_HEADER)
        cp.write(f)


def load_config() -> dict:
    """Return the active configuration dict. Side-effect: creates config.ini on
    first run after prompting the user."""
    path = config_path()
    if not path.exists():
        lang = _ask_language()
        try:
            _write_config(lang)
        except OSError:
            # read-only location — fall back to in-memory default
            pass
        return {"language": lang}

    cp = configparser.ConfigParser()
    try:
        cp.read(path, encoding="utf-8")
    except (configparser.Error, OSError):
        return {"language": DEFAULT_LANG}

    lang = (cp.get("General", "language", fallback=DEFAULT_LANG) or DEFAULT_LANG).strip().lower()
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    return {"language": lang}
