"""
Network plumbing: enumerate physical NICs, set / revert IP via netsh, ping hosts.

Pure functions; no shared state. The ping loop is in `dhcp.py` because it
mutates the DHCP server's client table."""

from __future__ import annotations
import json
import os
import subprocess
from typing import Any

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# Adapters we never show in the picker.
SKIP_DESCRIPTION = (
    "VPN", "Virtual", "AnyConnect", "TAP-", "TUN-", "Bluetooth", "Loopback",
    "WAN Miniport", "Hyper-V", "VMware", "VirtualBox", "WireGuard", "OpenVPN",
    "Tailscale", "ZeroTier",
)
SKIP_MEDIA = ("Native 802.11", "Wireless WAN")


def _run_ps(cmd: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )


def _run_netsh(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["netsh", *args],
        capture_output=True, text=True, timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )


def list_adapters() -> list[dict[str, Any]]:
    """Return physical wired adapters only — skip wireless / VPN / virtual."""
    cmd = (
        r"Get-NetAdapter | ForEach-Object {"
        r"  $ip = (Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
        r"        Where-Object PrefixOrigin -ne 'WellKnown' | Select-Object -ExpandProperty IPAddress) -join ','; "
        r"  [pscustomobject]@{"
        r"    Name=$_.Name; Description=$_.InterfaceDescription; Status=$_.Status; "
        r"    Virtual=[bool]$_.Virtual; MediaType=$_.MediaType; ifIndex=$_.ifIndex; IPv4=$ip"
        r"  }} | ConvertTo-Json -Depth 3 -Compress"
    )
    r = _run_ps(cmd, timeout=20)
    if r.returncode != 0 or not r.stdout.strip():
        return []
    data = json.loads(r.stdout)
    if isinstance(data, dict):
        data = [data]

    out: list[dict[str, Any]] = []
    for a in data:
        if a.get("Status") in ("Disabled", "Not Present"):
            continue
        if a.get("Virtual"):
            continue
        if a.get("MediaType") in SKIP_MEDIA:
            continue
        haystack = ((a.get("Description") or "") + " " + (a.get("Name") or "")).lower()
        if any(k.lower() in haystack for k in SKIP_DESCRIPTION):
            continue
        out.append(a)
    out.sort(key=lambda x: x["ifIndex"])
    return out


def set_static_ip(nic_name: str, ip: str, mask: str) -> None:
    _run_netsh(["interface", "ipv4", "set", "address", f"name={nic_name}", "static", ip, mask])


def revert_to_dhcp(nic_name: str) -> None:
    _run_netsh(["interface", "ipv4", "set", "address",    f"name={nic_name}", "source=dhcp"])
    _run_netsh(["interface", "ipv4", "set", "dnsservers", f"name={nic_name}", "source=dhcp"])


def ping_one(ip: str, timeout_ms: int = 600) -> bool:
    """Windows-`ping` based reachability test.

    Windows' `ping` exit code is unreliable — it can return 0 with
    "Destination host unreachable" or with a stale-ARP-based reply from the
    local stack. The only trustworthy success marker is the `TTL=` substring
    in stdout (present across locales — e.g. `...time<1ms TTL=64` or
    `...время<1мс TTL=64`)."""
    try:
        if os.name == "nt":
            cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
        else:
            cmd = ["ping", "-c", "1", "-W", "1", ip]
        r = subprocess.run(
            cmd, capture_output=True, timeout=2, text=True,
            creationflags=CREATE_NO_WINDOW,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return "TTL=" in out
    except Exception:
        return False
