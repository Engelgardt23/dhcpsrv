"""
Application entry: wires admin check, update check, NIC selection, the DHCP
server, the UI and the ping loop together."""

from __future__ import annotations
import signal
import sys
import threading

from rich.console import Console
from rich.prompt  import Confirm, Prompt

from .              import __version__
from .platform_win  import enable_vt, require_admin
from .update_check  import check_for_update
from .network       import list_adapters, set_static_ip, revert_to_dhcp
from .dhcp          import DhcpConfig, DhcpServer, now_s
from .ui            import Ui


def _select_nic(console: Console) -> dict | None:
    console.rule("[bold cyan]Available adapters")
    adapters = list_adapters()
    if not adapters:
        console.print("[red]No suitable wired adapters found.[/]")
        return None
    for i, a in enumerate(adapters, 1):
        ip = a.get("IPv4") or "—"
        console.print(f"  {i}) [{a['Status']}] {a['Name']}  ({a['Description']})  {ip}")
    while True:
        s = Prompt.ask("Select adapter number").strip()
        if s.isdigit() and 1 <= int(s) <= len(adapters):
            return adapters[int(s) - 1]
        console.print("[red]Invalid selection.[/]")


def main() -> None:
    enable_vt()
    require_admin()

    console = Console(log_path=False)
    console.print(f"[bold cyan]dhcpsrv v{__version__}[/] - portable laptop-side DHCP server")
    console.print("[dim]made by engelgardt[/]")
    console.print()

    check_for_update(console)

    nic = _select_nic(console)
    if not nic:
        input("Press Enter to exit"); return

    cfg = DhcpConfig.with_defaults()
    console.print(f"[yellow]Setting {nic['Name']} → {cfg.server_ip} / {cfg.netmask} ...[/]")
    set_static_ip(nic["Name"], cfg.server_ip, cfg.netmask)

    # Wire server <-> ui through callbacks so neither imports the other.
    ui     = Ui.__new__(Ui)        # forward declaration so server callbacks can capture it
    server = DhcpServer(cfg=cfg, log=lambda m: ui.log(m), on_change=lambda: ui.request_refresh())
    Ui.__init__(ui, server)        # finish UI init now that server exists

    stop = threading.Event()
    threading.Thread(target=server.run,        args=(stop,), daemon=True).start()
    threading.Thread(target=server.ping_loop,  args=(stop,), daemon=True).start()

    def shutdown(sig=None, frm=None):
        stop.set()
        try:
            print()
            print(f"[{now_s()}] Shutting down...")
            try:
                if Confirm.ask(f"Revert {nic['Name']} back to DHCP?", default=False):
                    revert_to_dhcp(nic["Name"])
                    print("NIC reverted to DHCP")
            except (EOFError, KeyboardInterrupt):
                pass
        finally:
            input("Press Enter to exit")
            sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        ui.run(stop)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
