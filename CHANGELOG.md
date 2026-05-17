# Changelog

All notable changes to **dhcpsrv** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.1] - 2026-05-16
### Changed
- The persistent header panel no longer prints the `made by engelgardt` line. Author credit moves to the one-off startup banner and the README only — the always-on UI stays tighter.

## [1.1.0] - 2026-05-16
### Added
- Auto-update check on startup. Polls GitHub `/releases/latest` with a 3-second timeout. If a newer version is available, prints a yellow notice and offers to open the download page in your browser. Silent on offline / API errors.

## [1.0.0] - 2026-05-16
### Added
- First public release on GitHub.
- Single portable `.exe` (~12 MB) — no Python required on target machines.
- Full-screen TUI built on `rich`: header with server config + live counters (Leases / Pkts / DISCOVER / REQUEST / RELEASE), clients table (`#`, IP, Hostname, MAC, Last seen, Ping), scrolling events panel.
- Hardcoded sensible defaults: server `10.10.10.1/24`, pool `10.10.10.2..10.10.10.51` (50 addresses), lease `7200 s`, TFTP option (66/150) = server IP.
- Only one prompt at startup: NIC selection.
- Adapter filter — only physical wired NICs appear in the picker (no Wi-Fi, VPN, virtual, Hyper-V, VMware, VirtualBox, TAP/TUN, WireGuard, OpenVPN, Tailscale, ZeroTier, Bluetooth, Loopback, WAN Miniport).
- Reliable ping check via the `TTL=` substring in `ping` output — a real BMC reboot is reflected as red `--`.
- Pure event-driven UI refresh — no flicker on resize or while idle.
- Auto-fit clients table to terminal height (`(+N more — enlarge the window)` marker on overflow).
- Scrollback cleared on startup so mouse-wheel doesn't expose pre-launch text.
- MIT licensed.

[Unreleased]: https://github.com/Engelgardt23/dhcpsrv/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Engelgardt23/dhcpsrv/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Engelgardt23/dhcpsrv/releases/tag/v1.0.0
