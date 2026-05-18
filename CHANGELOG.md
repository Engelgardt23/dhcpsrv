# Changelog

All notable changes to **dhcpsrv** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.1] - 2026-05-18
### Changed
- The `Update available (vX.Y.Z)` hint in the header is now a clickable hyperlink that opens the GitHub releases page (OSC 8 terminal hyperlink). Modern terminals (Windows Terminal, VS Code, WezTerm, most Linux/macOS terminals) render it as a link — `Ctrl+Click` to follow. Older consoles show the plain text, so nothing breaks.
- Russian tagline tightened: dropped the `для инженера` phrase, the wording was carried over from an earlier draft and felt out of place.

## [1.2.0] - 2026-05-18
### Added
- Russian UI translation. On first launch the application asks which language to use (`1) English`, `2) Русский`) and writes the answer to a fresh `config.ini` next to `dhcpsrv.exe`. To change the language later, edit `language = en` / `language = ru` in that file — the comment at the top of the file explains how, in both languages.
- `config.ini` becomes the future home for other settable defaults (pool, lease, server IP) — currently only `[General] language` is consumed.
- Bilingual `README.ru.md` linked from the main `README.md`.

## [1.1.3] - 2026-05-17
### Changed
- Update check no longer interrupts startup with an interactive prompt. If a newer release is available, the header line now shows a quiet `update available (vX.Y.Z)` hint right-aligned in dim grey — no key press required.
### Fixed
- Bumped `__version__` from `1.1.1` to `1.1.3` after the v1.1.2 release packaged a binary that still self-reported as v1.1.1 (the source constant was not bumped before tagging). The source is now once again the single source of truth.

## [1.1.2] - 2026-05-17
### Changed
- Dropped the `made by engelgardt` line from the startup banner too — author credit lives in the README only.
### Added
- Embedded application icon in the exe (via PyInstaller `--icon assets/icon.ico`).

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

[Unreleased]: https://github.com/Engelgardt23/dhcpsrv/compare/v1.2.1...HEAD
[1.2.1]: https://github.com/Engelgardt23/dhcpsrv/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/Engelgardt23/dhcpsrv/compare/v1.1.3...v1.2.0
[1.1.3]: https://github.com/Engelgardt23/dhcpsrv/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/Engelgardt23/dhcpsrv/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/Engelgardt23/dhcpsrv/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/Engelgardt23/dhcpsrv/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Engelgardt23/dhcpsrv/releases/tag/v1.0.0
