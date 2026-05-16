"""
dhcpsrv v1.1.0 - portable single-exe edition.
made by engelgardt

This file combines what previously lived in dhcpsrv.ps1 + dhcpsrv.py:
  - admin check
  - NIC selection (filters out wireless / VPN / virtual)
  - static IP setting (netsh)
  - DHCP server with rich live UI
  - revert NIC prompt on exit

Build:
  pyinstaller --onefile --uac-admin --name dhcpsrv --console dhcpsrv_app.py
"""

import os, sys, ctypes, json, subprocess, signal, socket, struct, threading, time
import urllib.request, webbrowser
from collections import deque
from datetime  import datetime
from concurrent.futures import ThreadPoolExecutor


# Enable VT (ANSI escape) processing on Windows console BEFORE any output.
def _enable_vt():
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
_enable_vt()

__version__ = "1.1.0"
GITHUB_REPO  = "Engelgardt23/dhcpsrv"

# Fixed heights used by the Layout — used to compute the clients table fit
HEADER_LINES = 5
EVENTS_LINES = 14
TBL_OVERHEAD = 6   # panel borders + table header row + table top/bottom rules

# Hardcoded defaults — pick NIC, everything else is auto.
DEFAULT_SERVER_IP = "10.10.10.1"
DEFAULT_NETMASK   = "255.255.255.0"
POOL_SIZE         = 50            # addresses starting at server_ip + 1
DEFAULT_LEASE     = 7200          # 2 hours
# TFTP option always = server IP

# Stats counters
stats = {"packets": 0, "discovers": 0, "requests": 0, "releases": 0}

# rich
try:
    from rich.console import Console, Group
    from rich.live    import Live
    from rich.table   import Table
    from rich.text    import Text
    from rich.panel   import Panel
    from rich.layout  import Layout
    from rich.prompt  import Prompt, Confirm
except ImportError:
    print("'rich' missing in the bundled build")
    input("Press Enter to exit")
    sys.exit(10)

console = Console(log_path=False)


# ---------- admin ----------
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except: return False

def require_admin():
    if not is_admin():
        # Re-launch elevated; original exits
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1)
        sys.exit(0)


# ---------- update check ----------
def _parse_version(s):
    try:
        s = (s or "").strip().lstrip("v")
        return tuple(int(x) for x in s.split(".")[:3])
    except Exception:
        return (0, 0, 0)

def check_for_update():
    """Query GitHub for the latest release. If newer than __version__, prompt to open the page."""
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
        # Offline / GitHub rate-limit / API error — skip silently.
        pass


# ---------- helpers ----------
CREATE_NO_WINDOW = 0x08000000
def run_ps(cmd, timeout=15):
    return subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",cmd],
                          capture_output=True, text=True, timeout=timeout,
                          creationflags=CREATE_NO_WINDOW)

def run_netsh(args, timeout=15):
    return subprocess.run(["netsh"] + args, capture_output=True, text=True,
                          timeout=timeout, creationflags=CREATE_NO_WINDOW)


# ---------- NIC enumeration ----------
SKIP_DESCR = ("VPN","Virtual","AnyConnect","TAP-","TUN-","Bluetooth","Loopback",
              "WAN Miniport","Hyper-V","VMware","VirtualBox","WireGuard","OpenVPN",
              "Tailscale","ZeroTier")
SKIP_MEDIA = ("Native 802.11","Wireless WAN")

def list_adapters():
    cmd = (r"Get-NetAdapter | ForEach-Object {"
           r"  $ip = (Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
           r"        Where-Object PrefixOrigin -ne 'WellKnown' | Select-Object -ExpandProperty IPAddress) -join ','; "
           r"  [pscustomobject]@{"
           r"    Name=$_.Name; Description=$_.InterfaceDescription; Status=$_.Status; "
           r"    Virtual=[bool]$_.Virtual; MediaType=$_.MediaType; ifIndex=$_.ifIndex; IPv4=$ip"
           r"  }} | ConvertTo-Json -Depth 3 -Compress")
    r = run_ps(cmd, timeout=20)
    if r.returncode != 0 or not r.stdout.strip():
        return []
    data = json.loads(r.stdout)
    if isinstance(data, dict): data = [data]
    out = []
    for a in data:
        if a["Status"] in ("Disabled","Not Present"): continue
        if a.get("Virtual"): continue
        if a.get("MediaType") in SKIP_MEDIA: continue
        descr = (a.get("Description") or "") + " " + (a.get("Name") or "")
        if any(k.lower() in descr.lower() for k in SKIP_DESCR): continue
        out.append(a)
    out.sort(key=lambda x: x["ifIndex"])
    return out


# ---------- DHCP server state ----------
clients      = {}        # mac -> {ip_int, host, last, ping_ok}
clients_lock = threading.Lock()
events       = deque(maxlen=200)
events_lock  = threading.Lock()
refresh_evt  = threading.Event()    # set whenever UI should re-render

def log_event(markup_line):
    with events_lock:
        events.append(markup_line)
    refresh_evt.set()

# Config (filled by main)
SERVER_IP = ""
NETMASK   = "255.255.255.0"
POOL      = []
LEASE     = 7200
TFTP      = ""

def ip2int(ip): return struct.unpack("!I", socket.inet_aton(ip))[0]
def int2ip(n):  return socket.inet_ntoa(struct.pack("!I", n))
def now_s():    return datetime.now().strftime("%H:%M:%S")


# ---------- ping ----------
# Windows `ping` exit code is unreliable: it can return 0 with "Destination host
# unreachable" or with a stale ARP-based "reply" from the local stack. The only
# trustworthy success marker is the "TTL=" substring in stdout (present across
# locales — e.g. "...time<1ms TTL=64" / "...время<1мс TTL=64").
def ping_one(ip, timeout_ms=600):
    try:
        r = subprocess.run(["ping","-n","1","-w",str(timeout_ms),ip],
                           capture_output=True, timeout=2, text=True,
                           creationflags=CREATE_NO_WINDOW)
        out = (r.stdout or "") + (r.stderr or "")
        return "TTL=" in out
    except Exception:
        return False

def ping_loop():
    pool_exec = ThreadPoolExecutor(max_workers=16)
    while True:
        with clients_lock:
            items = [(m, c["ip_int"]) for m, c in clients.items()]
        changed = False
        if items:
            ips = [int2ip(i) for _, i in items]
            res = list(pool_exec.map(ping_one, ips))
            with clients_lock:
                for (mac, _), ok in zip(items, res):
                    if mac in clients and clients[mac].get("ping_ok") != ok:
                        clients[mac]["ping_ok"] = ok
                        changed = True
        if changed:
            refresh_evt.set()
        time.sleep(1.0)


# ---------- DHCP logic ----------
def alloc_ip(mac):
    with clients_lock:
        if mac in clients: return clients[mac]["ip_int"]
        used = {c["ip_int"] for c in clients.values()}
        for ipn in POOL:
            if ipn not in used:
                clients[mac] = {"ip_int": ipn, "host": "", "last": now_s(), "ping_ok": False}
                return ipn
    return None

def touch_client(mac, ipn=None, host=None):
    with clients_lock:
        if mac not in clients:
            clients[mac] = {"ip_int": ipn or 0, "host": host or "", "last": now_s(), "ping_ok": False}
        else:
            clients[mac]["last"] = now_s()
            if ipn:  clients[mac]["ip_int"] = ipn
            if host: clients[mac]["host"]   = host

def parse_options(data):
    opts = {}; i = 240
    while i < len(data):
        code = data[i]
        if code == 0:   i += 1; continue
        if code == 255: break
        if i + 1 >= len(data): break
        L = data[i+1]
        opts[code] = data[i+2:i+2+L]
        i += 2 + L
    return opts

def get_hostname(opts):
    h = opts.get(12)
    if h:
        try: return h.rstrip(b"\x00").decode(errors="replace")
        except: return ""
    return ""

def build_reply(req, dhcp_type, yiaddr_int):
    pkt = bytearray(240)
    pkt[0] = 2; pkt[1] = 1; pkt[2] = 6; pkt[3] = 0
    pkt[4:8]   = req[4:8]
    pkt[10:12] = req[10:12]
    pkt[16:20] = struct.pack("!I", yiaddr_int)
    pkt[20:24] = socket.inet_aton(SERVER_IP)
    pkt[28:44] = req[28:44]
    pkt[236:240] = b"\x63\x82\x53\x63"
    o = bytearray()
    o += bytes([53,1,dhcp_type])
    o += bytes([54,4]) + socket.inet_aton(SERVER_IP)
    o += bytes([51,4]) + struct.pack("!I", LEASE)
    o += bytes([1,4])  + socket.inet_aton(NETMASK)
    o += bytes([3,4])  + socket.inet_aton(SERVER_IP)
    o += bytes([6,4])  + socket.inet_aton(SERVER_IP)
    tb = TFTP.encode()
    o += bytes([66, len(tb)]) + tb
    o += bytes([150,4]) + socket.inet_aton(TFTP)
    o += bytes([255])
    return bytes(pkt) + bytes(o)


# ---------- UI ----------
def render_table():
    t = Table(expand=True, header_style="bold")
    t.add_column("#",        style="dim", width=3, justify="right")
    t.add_column("IP",       width=16)
    t.add_column("Hostname", min_width=10)
    t.add_column("MAC",      width=19)
    t.add_column("Last seen",style="dim", width=10)
    t.add_column("Ping",     width=6, justify="center")
    with clients_lock:
        rows = sorted(clients.items(), key=lambda kv: kv[1]["ip_int"])

    # Auto-fit to available height (header + events panels are fixed-size in Layout).
    avail = max(1, console.size.height - HEADER_LINES - EVENTS_LINES - TBL_OVERHEAD)
    overflow = max(0, len(rows) - avail)
    if overflow:
        rows = rows[:avail - 1]   # leave one slot for the "(+N more)" marker

    if not rows:
        t.add_row("—","—","(no clients yet)","—","—","—")
    else:
        for i,(mac,c) in enumerate(rows,1):
            ping = Text("OK", style="bold green") if c.get("ping_ok") else Text("--", style="bold red")
            t.add_row(str(i), int2ip(c["ip_int"]), c.get("host") or "—", mac, c.get("last","—"), ping)
        if overflow:
            t.add_row("…", "", f"[dim](+{overflow} more — enlarge the window)[/]", "", "", "")
    return t

def render_header():
    with clients_lock:
        leased = len(clients)
    body = (f"[bold cyan]dhcpsrv v{__version__}[/]   [dim]made by engelgardt[/]\n"
            f"Server: [bold]{SERVER_IP}[/]/{NETMASK}    "
            f"Pool: [bold]{int2ip(POOL[0])}–{int2ip(POOL[-1])}[/]    "
            f"Lease: [bold]{LEASE}s[/]    "
            f"TFTP: [bold]{TFTP}[/]\n"
            f"Leases: [bold]{leased}/{len(POOL)}[/]    "
            f"Pkts: [dim]{stats['packets']}[/]    "
            f"DISCOVER: [cyan]{stats['discovers']}[/]    "
            f"REQUEST: [green]{stats['requests']}[/]    "
            f"RELEASE: [yellow]{stats['releases']}[/]    "
            f"[dim]Ctrl+C to stop[/]")
    return Panel(body, border_style="cyan")

def render_events_panel():
    with events_lock:
        last = list(events)[-20:]
    body = "\n".join(last) if last else "[dim](no events yet)[/]"
    return Panel(body, title="Events", border_style="dim")

def render_screen():
    layout = Layout()
    layout.split_column(
        Layout(render_header(),         name="hdr", size=HEADER_LINES),
        Layout(Panel(render_table(), title="Clients", border_style="cyan"), name="tbl"),
        Layout(render_events_panel(),   name="evt", size=EVENTS_LINES),
    )
    return layout

def ui_loop(stop):
    # Pure event-driven: refresh only on real state changes or terminal resize.
    # Clear screen AND scrollback so wheel-scrolling won't expose pre-launch text.
    sys.stdout.write("\x1b[2J\x1b[3J\x1b[H")
    sys.stdout.flush()

    last_size = console.size
    with Live(render_screen(), auto_refresh=False, console=console, screen=True,
              redirect_stdout=False, redirect_stderr=False) as live:
        live.refresh()
        while not stop.is_set():
            triggered = refresh_evt.wait(timeout=0.5)
            if stop.is_set(): break

            # Detect window resize without spamming refreshes
            cur_size = console.size
            resized  = (cur_size != last_size)
            if resized:
                last_size = cur_size

            if triggered:
                refresh_evt.clear()

            if triggered or resized:
                live.update(render_screen(), refresh=True)


# ---------- main flow ----------
def select_nic():
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
            return adapters[int(s)-1]
        console.print("[red]Invalid selection.[/]")

def set_static_ip(nic_name, ip, mask):
    console.print(f"[yellow]Setting {nic_name} → {ip} / {mask} ...[/]")
    run_netsh(["interface","ipv4","set","address",f"name={nic_name}","static",ip,mask])

def revert_dhcp(nic_name):
    run_netsh(["interface","ipv4","set","address",f"name={nic_name}","source=dhcp"])
    run_netsh(["interface","ipv4","set","dnsservers",f"name={nic_name}","source=dhcp"])

def main():
    global SERVER_IP, POOL, LEASE, TFTP
    require_admin()

    console.print(f"[bold cyan]dhcpsrv v{__version__}[/] - portable laptop-side DHCP server")
    console.print("[dim]made by engelgardt[/]")
    console.print()

    check_for_update()

    nic = select_nic()
    if not nic: input("Press Enter to exit"); return

    SERVER_IP = DEFAULT_SERVER_IP
    LEASE     = DEFAULT_LEASE
    TFTP      = SERVER_IP
    server_n  = ip2int(SERVER_IP)
    POOL      = list(range(server_n + 1, server_n + 1 + POOL_SIZE))

    set_static_ip(nic["Name"], SERVER_IP, NETMASK)
    log_event(f"[dim][{now_s()}][/] [bold]NIC[/] {nic['Name']} → {SERVER_IP}/{NETMASK}")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        s.bind(("0.0.0.0", 67))
    except OSError as e:
        console.print(f"[bold red]bind UDP/67 failed:[/] {e}")
        console.print("[yellow]Another DHCP service (Tftpd32, ICS, Windows DHCP) may be running.[/]")
        input("Press Enter to exit"); return

    stop = threading.Event()
    threading.Thread(target=ping_loop, daemon=True).start()
    threading.Thread(target=ui_loop, args=(stop,), daemon=True).start()

    def shutdown(sig=None, frm=None):
        stop.set()
        console.print()
        console.print(f"[dim][{now_s()}] Shutting down...[/]")
        try: s.close()
        except: pass
        # Ask revert
        try:
            if Confirm.ask(f"Revert {nic['Name']} back to DHCP?", default=False):
                revert_dhcp(nic["Name"])
                console.print("[green]NIC reverted to DHCP[/]")
        except (EOFError, KeyboardInterrupt): pass
        input("Press Enter to exit")
        sys.exit(0)
    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        try:
            data, _ = s.recvfrom(2048)
        except KeyboardInterrupt:
            shutdown(); return
        except OSError:
            continue
        if len(data) < 240 or data[0] != 1: continue
        stats["packets"] += 1
        mac = ":".join(f"{b:02x}" for b in data[28:34])
        opts = parse_options(data)
        msg = opts.get(53)
        if not msg: continue
        mt = msg[0]
        host = get_hostname(opts)
        host_s = f" [{host}]" if host else ""

        if mt == 1:
            stats["discovers"] += 1
            ipn = alloc_ip(mac)
            if ipn is None:
                log_event(f"[dim][{now_s()}][/] [red]DISCOVER[/] {mac} → [red]POOL EXHAUSTED[/]")
                continue
            touch_client(mac, ipn, host)
            s.sendto(build_reply(data, 2, ipn), ("255.255.255.255", 68))
            log_event(f"[dim][{now_s()}][/] [cyan]DISCOVER[/] {mac}{host_s} → OFFER {int2ip(ipn)}")
        elif mt == 3:
            stats["requests"] += 1
            req_ip = opts.get(50)
            with clients_lock:
                cached = clients.get(mac, {}).get("ip_int")
            ipn = struct.unpack("!I", req_ip)[0] if req_ip else cached
            if ipn is None: continue
            touch_client(mac, ipn, host)
            s.sendto(build_reply(data, 5, ipn), ("255.255.255.255", 68))
            log_event(f"[dim][{now_s()}][/] [green]REQUEST[/]  {mac}{host_s} → ACK {int2ip(ipn)}")
        elif mt == 7:
            stats["releases"] += 1
            with clients_lock:
                old = clients.pop(mac, None)
            if old:
                log_event(f"[dim][{now_s()}][/] [yellow]RELEASE[/]  {mac} → freed {int2ip(old['ip_int'])}")
        elif mt == 8:
            log_event(f"[dim][{now_s()}][/] [blue]INFORM[/]   {mac}{host_s}")

if __name__ == "__main__":
    main()
