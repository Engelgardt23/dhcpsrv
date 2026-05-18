"""
Tiny in-memory translation table. We do not need .po/.mo machinery for a
two-language CLI tool — a flat dict per language is enough.

Usage:
    from .i18n import t, set_language
    set_language("ru")
    print(t("no_adapters"))

`t(key, **params)` performs `.format(**params)` on the returned string, so
placeholders work the same way as f-strings.
"""

from __future__ import annotations


_lang = "en"

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # app.py / startup
        "tagline":              "- portable laptop-side DHCP server",
        "update_available":     "Update available ({tag})",
        "available_adapters":   "Available adapters",
        "no_adapters":          "No suitable wired adapters found.",
        "select_adapter":       "Select adapter number",
        "invalid_selection":    "Invalid selection.",
        "press_enter":          "Press Enter to exit",
        "setting_nic":          "Setting {name} → {ip} / {mask} ...",
        "shutting_down":        "[{ts}] Shutting down...",
        "revert_nic":           "Revert {name} back to DHCP?",
        "nic_reverted":         "NIC reverted to DHCP",

        # dhcp.py / server messages
        "bind_failed":          "bind UDP/67 failed:",
        "bind_hint":            "Another DHCP service (Tftpd32 DHCP, ICS, Windows DHCP) may be running.",
        "pool_exhausted":       "POOL EXHAUSTED",

        # ui.py / header & panels
        "panel_server":         "Server",
        "panel_pool":           "Pool",
        "panel_lease":          "Lease",
        "panel_tftp":           "TFTP",
        "panel_leases":         "Leases",
        "panel_pkts":           "Pkts",
        "panel_ctrlc":          "Ctrl+C to stop",
        "col_ip":               "IP",
        "col_host":             "Hostname",
        "col_mac":              "MAC",
        "col_last":             "Last seen",
        "col_ping":             "Ping",
        "no_clients":           "(no clients yet)",
        "more_clients":         "(+{n} more — enlarge the window)",
        "events_title":         "Events",
        "clients_title":        "Clients",
        "no_events":            "(no events yet)",
    },
    "ru": {
        "tagline":              "— портативный DHCP-сервер",
        "update_available":     "Доступно обновление ({tag})",
        "available_adapters":   "Доступные адаптеры",
        "no_adapters":          "Подходящие проводные адаптеры не найдены.",
        "select_adapter":       "Введите номер адаптера",
        "invalid_selection":    "Неверный выбор.",
        "press_enter":          "Нажмите Enter для выхода",
        "setting_nic":          "Назначаю {name} → {ip} / {mask} ...",
        "shutting_down":        "[{ts}] Завершение работы...",
        "revert_nic":           "Вернуть {name} обратно в режим DHCP?",
        "nic_reverted":         "Адаптер возвращён в режим DHCP",

        "bind_failed":          "не удалось занять UDP/67:",
        "bind_hint":             "Возможно, уже запущен другой DHCP (модуль DHCP в Tftpd32, ICS, Windows DHCP).",
        "pool_exhausted":       "ПУЛ ИСЧЕРПАН",

        "panel_server":         "Сервер",
        "panel_pool":           "Пул",
        "panel_lease":          "Аренда",
        "panel_tftp":           "TFTP",
        "panel_leases":         "Аренды",
        "panel_pkts":           "Пакетов",
        "panel_ctrlc":          "Ctrl+C — выход",
        "col_ip":               "IP",
        "col_host":             "Имя хоста",
        "col_mac":              "MAC",
        "col_last":             "Последний",
        "col_ping":             "Пинг",
        "no_clients":           "(клиентов пока нет)",
        "more_clients":         "(ещё +{n} — увеличьте окно)",
        "events_title":         "События",
        "clients_title":        "Клиенты",
        "no_events":            "(пока пусто)",
    },
}


def set_language(lang: str) -> None:
    global _lang
    if lang in STRINGS:
        _lang = lang


def language() -> str:
    return _lang


def t(key: str, **params) -> str:
    """Translate `key` for the active language; fall back to English if a key is
    missing in the chosen language. Apply `.format(**params)` for placeholders."""
    s = STRINGS.get(_lang, {}).get(key) or STRINGS["en"].get(key, key)
    if params:
        try:
            return s.format(**params)
        except (KeyError, IndexError):
            return s
    return s
