"""Cornerplay.exe's entry point (PyInstaller). The same as `python -m cornerplay`, and the
helpers Cornerplay starts for itself (Cornerplay.exe --run-module cornerplay.session ...)."""
import sys

from cornerplay.osinfo import run_frozen_helper

if __name__ == "__main__":
    if run_frozen_helper():
        sys.exit(0)
    from cornerplay.__main__ import main
    sys.exit(main())
