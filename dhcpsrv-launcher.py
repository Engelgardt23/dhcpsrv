"""
PyInstaller entry point — sits at the repo root and uses an *absolute* import
so the bundled exe doesn't need relative-import resolution at runtime.

For dev work without an install use `python -m dhcpsrv` instead (that path
goes through `src/dhcpsrv/__main__.py` and relative imports work).
"""

from dhcpsrv.app import main


if __name__ == "__main__":
    main()
