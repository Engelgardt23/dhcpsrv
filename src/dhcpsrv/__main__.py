"""Entry point for `python -m dhcpsrv` from a checked-out / installed package.

The PyInstaller-bundled exe uses `dhcpsrv-launcher.py` at the repo root instead,
because PyInstaller runs the bundled script as a standalone module — relative
imports fail there."""

from .app import main


if __name__ == "__main__":
    main()
