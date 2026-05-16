# Contributing

> Project layout, build, and release flow. **If you only want to use the tool — read [README](README.md) instead.**

## Repo layout

```
dhcpsrv/
├── .github/
│   ├── workflows/release.yml          ← CI: tag-driven build + GitHub Release
│   └── ISSUE_TEMPLATE/                ← bug / feature / security routing
├── src/dhcpsrv/                       ← package source (≤200 lines per module)
│   ├── __init__.py                    ← single source of truth for __version__
│   ├── __main__.py                    ← entry: python -m dhcpsrv
│   ├── app.py                         ← main flow, wires everything
│   ├── platform_win.py                ← VT enable + UAC self-elevate
│   ├── update_check.py                ← GitHub /releases/latest poll
│   ├── network.py                     ← list_adapters, netsh, ping (no shared state)
│   ├── dhcp.py                        ← DhcpConfig, DhcpServer, packet parse/build
│   └── ui.py                          ← rich-based full-screen TUI
├── pyproject.toml                     ← deps, packaging, dynamic version
├── CHANGELOG.md                       ← Keep a Changelog format, newest first
├── CONTRIBUTING.md                    ← this file
├── LICENSE / README.md / SECURITY.md
└── .gitignore
```

## Run from source (no exe)

```
python -m pip install rich
python -m dhcpsrv
```

`python -m dhcpsrv` finds `src/dhcpsrv/__main__.py` because the package lives under `src/`. You'll need administrator privileges for UDP/67 and `netsh` — the tool self-elevates via UAC.

## Editable install (development)

```
python -m pip install -e .
dhcpsrv
```

`-e .` makes the entry-point `dhcpsrv` available on PATH; edits in `src/dhcpsrv/` take effect immediately.

## Build the portable .exe

```
python -m pip install pyinstaller rich
python -m PyInstaller --onefile --uac-admin --console --name dhcpsrv --paths src dhcpsrv-launcher.py
```

`dhcpsrv-launcher.py` (at repo root) is the PyInstaller entry — it does an
*absolute* import (`from dhcpsrv.app import main`) which is needed when
PyInstaller runs the bundled script as a standalone module. The `--paths src`
flag tells PyInstaller where to find the `dhcpsrv` package itself. Output:
`dist/dhcpsrv.exe`.

## Cut a release

1. Update `src/dhcpsrv/__init__.py` — bump `__version__` to `X.Y.Z`.
2. Update `CHANGELOG.md` — move items from `[Unreleased]` into a new `[X.Y.Z]` section with today's date.
3. Commit: `git commit -am "vX.Y.Z: …"`.
4. Tag: `git tag vX.Y.Z`.
5. Push: `git push && git push --tags`.

That's it. GitHub Actions picks up the tag, builds the exe, writes the SHA-256, and creates the GitHub Release with the zip attached.

## Where features go

| Adding... | Touch this module |
|---|---|
| A new DHCP option in the reply | `dhcp.py` → `DhcpServer.build_reply` |
| A new adapter filter | `network.py` → `SKIP_DESCRIPTION` / `SKIP_MEDIA` / `list_adapters` |
| A new column in the clients table | `ui.py` → `Ui._render_table` |
| Something shown in the header | `ui.py` → `Ui._render_header` |
| A startup check or banner line | `app.py` → `main()` |
| A change to UAC / VT logic | `platform_win.py` |
| Tweaking the GitHub update-check UX | `update_check.py` |
