# dhcpsrv

[![Latest release](https://img.shields.io/github/v/release/Engelgardt23/dhcpsrv)](https://github.com/Engelgardt23/dhcpsrv/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

🇺🇸 English | [🇷🇺 Русский](README.ru.md)

A tiny portable **DHCP server** for the laptop of a storage/server engineer.
One double-click — pick a NIC — done. Live table of clients, ping status, packet counters. No install, no Python required on the target machine.

Built for the “plug the cable in, watch a BMC pop up with an IP” workflow during firmware updates, recovery, and benchmarks.

> **Made by engelgardt.**

---

## Download

Grab the latest release: [**releases page**](https://github.com/Engelgardt23/dhcpsrv/releases/latest).
The asset is `dhcpsrv-portable-vX.Y.Z.zip` (~12 MB).

## Run

1. Unzip anywhere.
2. Double-click `dhcpsrv.exe`.
3. Accept the UAC prompt (admin is needed to bind UDP/67 and reconfigure the NIC).
4. Pick the network adapter wired to your server or switch — that's the only question.
5. `Ctrl+C` to stop. You'll be asked whether to revert the NIC to DHCP.

## Defaults (no other prompts)

| Parameter | Value |
|---|---|
| Server IP   | `10.10.10.1/24` |
| Pool        | `10.10.10.2 .. 10.10.10.51` (50 addresses) |
| Lease       | `7200 s` (2 hours — survives long stress tests) |
| TFTP option | server IP (BMC will see your Tftpd32 immediately) |

## What's on screen

```
┌─ dhcpsrv v1.0.0  made by engelgardt ────────────────────────────────────┐
│ Server: 10.10.10.1/255.255.255.0  Pool: 10.10.10.2–10.10.10.51 …        │
│ Leases: 3/50  Pkts: 47  DISCOVER: 12  REQUEST: 11  RELEASE: 0           │
└─────────────────────────────────────────────────────────────────────────┘
┌─ Clients ───────────────────────────────────────────────────────────────┐
│  # │ IP           │ Hostname     │ MAC               │ Last seen │ Ping │
│  1 │ 10.10.10.2   │ server-01    │ a0:c5:f2:13:57:46 │ 17:42:18  │  OK  │
│  2 │ 10.10.10.3   │ server-02    │ 70:b3:d5:11:22:33 │ 17:42:21  │  --  │
└─────────────────────────────────────────────────────────────────────────┘
┌─ Events ────────────────────────────────────────────────────────────────┐
│ [17:42:18] DISCOVER a0:c5:f2:13:57:46 → OFFER 10.10.10.2                │
│ [17:42:18] REQUEST  a0:c5:f2:13:57:46 → ACK   10.10.10.2                │
└─────────────────────────────────────────────────────────────────────────┘
```

## Typical scenarios

- **Server with shared LOM** — one cable into the BMC/host port, BMC and the host OS both get IPs from this DHCP.
- **8-port switch** — laptop on one port, up to 7 servers on the rest; the 50-address pool covers everyone.
- **Direct cable into a dedicated Mgmt port** — single client (the BMC).

## Compatibility

- Windows 10 / 11.
- Filters out wireless / VPN / virtual adapters from the picker (Wi-Fi, Cisco AnyConnect, Hyper-V, VMware, VirtualBox, TAP/TUN, WireGuard, OpenVPN, Tailscale, ZeroTier).
- NIC names with spaces or non-ASCII characters are quoted correctly for `netsh`.

## Notes

- Nothing is installed on your machine. Delete the folder to remove.
- The UAC prompt appears every time. (If you want it gone on *your* machine, wire `dhcpsrv.exe` through a Scheduled Task with “Run with highest privileges” and launch via `schtasks /run /tn dhcpsrv`.)
- If Tftpd32 has its DHCP module enabled, disable it — UDP/67 is then taken.
- Lease defaults to 7200 s; the client renews at half lease. If you want it effectively forever, the source supports `2147483647` — rebuild from source if you really need it.

## Build from source

```
python -m pip install rich pyinstaller
python -m PyInstaller --onefile --uac-admin --console --name dhcpsrv dhcpsrv_app.py
```

## License

MIT — see [LICENSE](LICENSE).
