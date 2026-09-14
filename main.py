"""Compatibility entry point; prefer the installed ``youai`` command."""

from youai.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
