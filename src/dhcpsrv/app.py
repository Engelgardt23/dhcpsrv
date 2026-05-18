"""
Application entry: wires admin check, update check, NIC selection, the DHCP
server, the UI and the ping loop together."""

from __future__ import annotations
import signal
import sys
import threading

from rich.console import Console
from rich.prompt  import Confirm, Prompt
from rich.table   import Table

from .              import __version__
from .platform_win  import enable_vt, require_admin
from .update_check  import check_for_update
from .network       import list_adapters, set_static_ip, revert_to_dhcp
from .dhcp          import DhcpConfig, DhcpServer, now_s
from .ui            import Ui
from .config        import load_config
from .i18n          import set_language, t


def _select_nic(console: Console) -> dict | None:
    console.rule(f"[bold cyan]{t('available_adapters')}")
    adapters = list_adapters()
    if not adapters:
        console.print(f"[red]{t('no_adapters')}[/]")
        return None
    for i, a in enumerate(adapters, 1):
        ip = a.get("IPv4") or "—"
        console.print(f"  {i}) [{a['Status']}] {a['Name']}  ({a['Description']})  {ip}")
    while True:
        s = Prompt.ask(t("select_adapter")).strip()
        if s.isdigit() and 1 <= int(s) <= len(adapters):
            return adapters[int(s) - 1]
        console.print(f"[red]{t('invalid_selection')}[/]")


def main() -> None:
    enable_vt()

    # Language prompt (writes config.ini on first run) happens BEFORE admin
    # elevation so the user does not have to answer it twice after the UAC
    # bounce.
    cfg_data = load_config()
    set_language(cfg_data["language"])

    require_admin()

    console = Console(log_path=False)

    title  = f"[bold cyan]dhcpsrv v{__version__}[/] {t('tagline')}"
    latest = check_for_update()
    if latest:
        header = Table.grid(expand=True)
        header.add_column(justify="left",  ratio=1)
        header.add_column(justify="right")
        header.add_row(title, f"[dim]{t('update_available', tag=latest)}[/]")
        console.print(header)
    else:
        console.print(title)
    console.print()

    nic = _select_nic(console)
    if not nic:
        input(t("press_enter")); return

    cfg = DhcpConfig.with_defaults()
    console.print(f"[yellow]{t('setting_nic', name=nic['Name'], ip=cfg.server_ip, mask=cfg.netmask)}[/]")
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
            print(t("shutting_down", ts=now_s()))
            try:
                if Confirm.ask(t("revert_nic", name=nic["Name"]), default=False):
                    revert_to_dhcp(nic["Name"])
                    print(t("nic_reverted"))
            except (EOFError, KeyboardInterrupt):
                pass
        finally:
            input(t("press_enter"))
            sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        ui.run(stop)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
