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
            f"[bold cyan]dhcpsrv v{__version__}[/]   [dim]made by engelgardt[/]\n"
            f"Server: [bold]{cfg.server_ip}[/]/{cfg.netmask}    "
            f"Pool: [bold]{int2ip(cfg.pool[0])}–{int2ip(cfg.pool[-1])}[/]    "
            f"Lease: [bold]{cfg.lease}s[/]    "
            f"TFTP: [bold]{cfg.tftp}[/]\n"
            f"Leases: [bold]{leased}/{len(cfg.pool)}[/]    "
            f"Pkts: [dim]{st['packets']}[/]    "
            f"DISCOVER: [cyan]{st['discovers']}[/]    "
            f"REQUEST: [green]{st['requests']}[/]    "
            f"RELEASE: [yellow]{st['releases']}[/]    "
            f"[dim]Ctrl+C to stop[/]"
        )
        return Panel(body, border_style="cyan")

    def _render_table(self) -> Table:
        t = Table(expand=True, header_style="bold")
        t.add_column("#",         style="dim", width=3,  justify="right")
        t.add_column("IP",        width=16)
        t.add_column("Hostname",  min_width=10)
        t.add_column("MAC",       width=19)
        t.add_column("Last seen", style="dim", width=10)
        t.add_column("Ping",      width=6,  justify="center")

        with self.server.lock:
            rows = sorted(self.server.clients.items(), key=lambda kv: kv[1]["ip_int"])

        avail    = max(1, self.console.size.height - HEADER_LINES - EVENTS_LINES - TBL_OVERHEAD)
        overflow = max(0, len(rows) - avail)
        if overflow:
            rows = rows[: avail - 1]   # leave one slot for the "(+N more)" marker

        if not rows:
            t.add_row("—", "—", "(no clients yet)", "—", "—", "—")
        else:
            for i, (mac, c) in enumerate(rows, 1):
                ping = (Text("OK", style="bold green")
                        if c.get("ping_ok") else Text("--", style="bold red"))
                t.add_row(
                    str(i),
                    int2ip(c["ip_int"]),
                    c.get("host") or "—",
                    mac,
                    c.get("last", "—"),
                    ping,
                )
            if overflow:
                t.add_row("…", "", f"[dim](+{overflow} more — enlarge the window)[/]", "", "", "")
        return t

    def _render_events(self) -> Panel:
        with self.events_lock:
            last = list(self.events)[-20:]
        body = "\n".join(last) if last else "[dim](no events yet)[/]"
        return Panel(body, title="Events", border_style="dim")

    def _render_screen(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(self._render_header(), name="hdr", size=HEADER_LINES),
            Layout(Panel(self._render_table(), title="Clients", border_style="cyan"), name="tbl"),
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
