"""
Rich-based full-screen TUI.

`Ui` owns the events buffer and the refresh trigger; it reads everything else
from the `DhcpServer` it's bound to."""

from __future__ import annotations
import sys
import threading
from collections import deque
from typing      import Callable

from rich.console import Console
from rich.layout  import Layout
from rich.live    import Live
from rich.panel   import Panel
from rich.table   import Table
from rich.text    import Text

from .         import __version__
from .dhcp     import DhcpServer, int2ip
from .i18n     import t as _t


# Fixed-size layout slots — used to compute the clients-table fit.
HEADER_LINES = 5
EVENTS_LINES = 14
TBL_OVERHEAD = 6   # panel borders + table header + table rules


class Ui:
    def __init__(self, server: DhcpServer):
        self.server      = server
        self.console     = Console(log_path=False)
        self.events      = deque(maxlen=200)
        self.events_lock = threading.Lock()
        self.refresh_evt = threading.Event()

    # --- public for other modules ---
    def log(self, markup: str) -> None:
        """Append an event line. Called from the DHCP server thread."""
        with self.events_lock:
            self.events.append(markup)
        self.refresh_evt.set()

    def request_refresh(self) -> None:
        """Called when something the UI cares about changed (e.g. a ping result)."""
        self.refresh_evt.set()

    # --- rendering ---
    def _render_header(self) -> Panel:
        with self.server.lock:
            leased = len(self.server.clients)
        st = self.server.stats
        cfg = self.server.cfg
        body = (
            f"[bold cyan]dhcpsrv v{__version__}[/]\n"
            f"{_t('panel_server')}: [bold]{cfg.server_ip}[/]/{cfg.netmask}    "
            f"{_t('panel_pool')}: [bold]{int2ip(cfg.pool[0])}–{int2ip(cfg.pool[-1])}[/]    "
            f"{_t('panel_lease')}: [bold]{cfg.lease}s[/]    "
            f"{_t('panel_tftp')}: [bold]{cfg.tftp}[/]\n"
            f"{_t('panel_leases')}: [bold]{leased}/{len(cfg.pool)}[/]    "
            f"{_t('panel_pkts')}: [dim]{st['packets']}[/]    "
            f"DISCOVER: [cyan]{st['discovers']}[/]    "
            f"REQUEST: [green]{st['requests']}[/]    "
            f"RELEASE: [yellow]{st['releases']}[/]    "
            f"[dim]{_t('panel_ctrlc')}[/]"
        )
        return Panel(body, border_style="cyan")

    def _render_table(self) -> Table:
        tbl = Table(expand=True, header_style="bold")
        tbl.add_column("#",              style="dim", width=3,  justify="right")
        tbl.add_column(_t("col_ip"),     width=16)
        tbl.add_column(_t("col_host"),   min_width=10)
        tbl.add_column(_t("col_mac"),    width=19)
        tbl.add_column(_t("col_last"),   style="dim", width=10)
        tbl.add_column(_t("col_ping"),   width=6,  justify="center")

        with self.server.lock:
            rows = sorted(self.server.clients.items(), key=lambda kv: kv[1]["ip_int"])

        avail    = max(1, self.console.size.height - HEADER_LINES - EVENTS_LINES - TBL_OVERHEAD)
        overflow = max(0, len(rows) - avail)
        if overflow:
            rows = rows[: avail - 1]   # leave one slot for the "(+N more)" marker

        if not rows:
            tbl.add_row("—", "—", _t("no_clients"), "—", "—", "—")
        else:
            for i, (mac, c) in enumerate(rows, 1):
                ping = (Text("OK", style="bold green")
                        if c.get("ping_ok") else Text("--", style="bold red"))
                tbl.add_row(
                    str(i),
                    int2ip(c["ip_int"]),
                    c.get("host") or "—",
                    mac,
                    c.get("last", "—"),
                    ping,
                )
            if overflow:
                tbl.add_row("…", "", f"[dim]{_t('more_clients', n=overflow)}[/]", "", "", "")
        return tbl

    def _render_events(self) -> Panel:
        with self.events_lock:
            last = list(self.events)[-20:]
        body = "\n".join(last) if last else f"[dim]{_t('no_events')}[/]"
        return Panel(body, title=_t("events_title"), border_style="dim")

    def _render_screen(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(self._render_header(), name="hdr", size=HEADER_LINES),
            Layout(Panel(self._render_table(), title=_t("clients_title"), border_style="cyan"), name="tbl"),
            Layout(self._render_events(),  name="evt", size=EVENTS_LINES),
        )
        return layout

    # --- main loop ---
    def run(self, stop: threading.Event) -> None:
        """Run until `stop` is set. Event-driven: redraws only on real changes
        or terminal resize."""
        # Clear screen + scrollback so wheel-scrolling can't expose pre-launch text.
        sys.stdout.write("\x1b[2J\x1b[3J\x1b[H")
        sys.stdout.flush()

        last_size = self.console.size
        with Live(self._render_screen(), auto_refresh=False, console=self.console,
                  screen=True, redirect_stdout=False, redirect_stderr=False) as live:
            live.refresh()
            while not stop.is_set():
                triggered = self.refresh_evt.wait(timeout=0.5)
                if stop.is_set():
                    break
                cur_size = self.console.size
                resized  = (cur_size != last_size)
                if resized:
                    last_size = cur_size
                if triggered:
                    self.refresh_evt.clear()
                if triggered or resized:
                    live.update(self._render_screen(), refresh=True)
