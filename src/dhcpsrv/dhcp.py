"""
DHCP server: packet parsing/building, the lease table, and the main socket
loop. Pure logic — UI rendering and ping live in their own modules.

The `DhcpServer` instance owns the runtime state (clients, stats). The UI
holds a reference to it and reads it whenever it renders."""

from __future__ import annotations
import socket
import struct
import sys
import threading
from dataclasses import dataclass, field
from datetime    import datetime
from typing      import Callable, Optional

from .network import ping_one


# ---------- helpers ----------
def ip2int(ip: str) -> int:
    return struct.unpack("!I", socket.inet_aton(ip))[0]


def int2ip(n: int) -> str:
    return socket.inet_ntoa(struct.pack("!I", n))


def now_s() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ---------- config ----------
@dataclass
class DhcpConfig:
    server_ip: str
    netmask:   str
    pool:      list[int]              # list of int IPs to hand out
    lease:     int                    # seconds
    tftp:      str                    # value for options 66 / 150

    @classmethod
    def with_defaults(cls, server_ip: str = "10.10.10.1",
                      netmask: str = "255.255.255.0",
                      pool_size: int = 50,
                      lease: int = 7200) -> "DhcpConfig":
        n = ip2int(server_ip)
        pool = list(range(n + 1, n + 1 + pool_size))
        return cls(server_ip=server_ip, netmask=netmask, pool=pool,
                   lease=lease, tftp=server_ip)


# ---------- server ----------
@dataclass
class DhcpServer:
    cfg:   DhcpConfig
    log:   Callable[[str], None]      # how to push an event line into the UI
    on_change: Callable[[], None]     # called whenever something the UI cares about changed

    clients: dict[str, dict] = field(default_factory=dict)
    lock:    threading.Lock = field(default_factory=threading.Lock)
    stats:   dict[str, int] = field(default_factory=lambda: {
        "packets": 0, "discovers": 0, "requests": 0, "releases": 0,
    })

    # --- lease allocation ---
    def alloc_ip(self, mac: str) -> Optional[int]:
        with self.lock:
            if mac in self.clients:
                return self.clients[mac]["ip_int"]
            used = {c["ip_int"] for c in self.clients.values()}
            for ipn in self.cfg.pool:
                if ipn not in used:
                    self.clients[mac] = {
                        "ip_int": ipn, "host": "", "last": now_s(), "ping_ok": False,
                    }
                    return ipn
        return None

    def touch_client(self, mac: str, ipn: Optional[int] = None, host: Optional[str] = None) -> None:
        with self.lock:
            if mac not in self.clients:
                self.clients[mac] = {
                    "ip_int": ipn or 0, "host": host or "",
                    "last": now_s(), "ping_ok": False,
                }
            else:
                self.clients[mac]["last"] = now_s()
                if ipn:  self.clients[mac]["ip_int"] = ipn
                if host: self.clients[mac]["host"]   = host

    def release_client(self, mac: str) -> Optional[int]:
        with self.lock:
            old = self.clients.pop(mac, None)
        return old["ip_int"] if old else None

    # --- packet parsing ---
    @staticmethod
    def parse_options(data: bytes) -> dict[int, bytes]:
        opts: dict[int, bytes] = {}
        i = 240
        while i < len(data):
            code = data[i]
            if code == 0:
                i += 1; continue
            if code == 255:
                break
            if i + 1 >= len(data):
                break
            L = data[i + 1]
            opts[code] = data[i + 2 : i + 2 + L]
            i += 2 + L
        return opts

    @staticmethod
    def get_hostname(opts: dict[int, bytes]) -> str:
        h = opts.get(12)
        if not h:
            return ""
        try:
            return h.rstrip(b"\x00").decode(errors="replace")
        except Exception:
            return ""

    # --- packet building ---
    def build_reply(self, req: bytes, dhcp_type: int, yiaddr_int: int) -> bytes:
        pkt = bytearray(240)
        pkt[0] = 2; pkt[1] = 1; pkt[2] = 6; pkt[3] = 0
        pkt[4:8]    = req[4:8]                                # xid
        pkt[10:12]  = req[10:12]                              # flags
        pkt[16:20]  = struct.pack("!I", yiaddr_int)           # yiaddr
        pkt[20:24]  = socket.inet_aton(self.cfg.server_ip)    # siaddr
        pkt[28:44]  = req[28:44]                              # chaddr
        pkt[236:240] = b"\x63\x82\x53\x63"                    # magic cookie

        o = bytearray()
        o += bytes([53, 1, dhcp_type])                                        # message type
        o += bytes([54, 4]) + socket.inet_aton(self.cfg.server_ip)            # server id
        o += bytes([51, 4]) + struct.pack("!I", self.cfg.lease)               # lease time
        o += bytes([1,  4]) + socket.inet_aton(self.cfg.netmask)              # subnet mask
        o += bytes([3,  4]) + socket.inet_aton(self.cfg.server_ip)            # router
        o += bytes([6,  4]) + socket.inet_aton(self.cfg.server_ip)            # DNS
        tftp = self.cfg.tftp.encode()
        o += bytes([66, len(tftp)]) + tftp                                    # TFTP server name
        o += bytes([150, 4]) + socket.inet_aton(self.cfg.tftp)                # TFTP server addr
        o += bytes([255])
        return bytes(pkt) + bytes(o)

    # --- ping loop, runs in its own thread ---
    def ping_loop(self, stop: threading.Event) -> None:
        from concurrent.futures import ThreadPoolExecutor
        pool_exec = ThreadPoolExecutor(max_workers=16)
        while not stop.wait(1.0):
            with self.lock:
                items = [(m, c["ip_int"]) for m, c in self.clients.items()]
            if not items:
                continue
            ips     = [int2ip(i) for _, i in items]
            results = list(pool_exec.map(ping_one, ips))
            changed = False
            with self.lock:
                for (mac, _), ok in zip(items, results):
                    if mac in self.clients and self.clients[mac].get("ping_ok") != ok:
                        self.clients[mac]["ping_ok"] = ok
                        changed = True
            if changed:
                self.on_change()

    # --- main server loop ---
    def run(self, stop: threading.Event) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            s.bind(("0.0.0.0", 67))
        except OSError as e:
            self.log(f"[bold red]bind UDP/67 failed:[/] {e}")
            self.log("[yellow]Another DHCP service (Tftpd32 DHCP, ICS, Windows DHCP) may be running.[/]")
            stop.set()
            return

        while not stop.is_set():
            try:
                data, _ = s.recvfrom(2048)
            except OSError:
                continue
            if len(data) < 240 or data[0] != 1:
                continue
            self.stats["packets"] += 1
            mac = ":".join(f"{b:02x}" for b in data[28:34])
            opts = self.parse_options(data)
            msg  = opts.get(53)
            if not msg:
                continue
            mt   = msg[0]
            host = self.get_hostname(opts)
            host_s = f" [{host}]" if host else ""

            if mt == 1:    # DISCOVER
                self.stats["discovers"] += 1
                ipn = self.alloc_ip(mac)
                if ipn is None:
                    self.log(f"[dim][{now_s()}][/] [red]DISCOVER[/] {mac} → [red]POOL EXHAUSTED[/]")
                    continue
                self.touch_client(mac, ipn, host)
                s.sendto(self.build_reply(data, 2, ipn), ("255.255.255.255", 68))
                self.log(f"[dim][{now_s()}][/] [cyan]DISCOVER[/] {mac}{host_s} → OFFER {int2ip(ipn)}")

            elif mt == 3:  # REQUEST
                self.stats["requests"] += 1
                req_ip = opts.get(50)
                with self.lock:
                    cached = self.clients.get(mac, {}).get("ip_int")
                ipn = struct.unpack("!I", req_ip)[0] if req_ip else cached
                if ipn is None:
                    continue
                self.touch_client(mac, ipn, host)
                s.sendto(self.build_reply(data, 5, ipn), ("255.255.255.255", 68))
                self.log(f"[dim][{now_s()}][/] [green]REQUEST[/]  {mac}{host_s} → ACK {int2ip(ipn)}")

            elif mt == 7:  # RELEASE
                self.stats["releases"] += 1
                old = self.release_client(mac)
                if old is not None:
                    self.log(f"[dim][{now_s()}][/] [yellow]RELEASE[/]  {mac} → freed {int2ip(old)}")

            elif mt == 8:  # INFORM
                self.log(f"[dim][{now_s()}][/] [blue]INFORM[/]   {mac}{host_s}")

            self.on_change()

        try:
            s.close()
        except Exception:
            pass
