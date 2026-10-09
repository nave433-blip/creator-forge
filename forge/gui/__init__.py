"""CreatorForge desktop GUI (PySide6/Qt, optional).

This module imports cleanly WITHOUT PySide6 installed -- the Qt import
happens lazily inside :func:`launch`. Run it with ``forge gui``.
"""

from __future__ import annotations


def launch(config_path: str | None = None) -> int:
    """Launch the desktop GUI. Returns the Qt exit code."""
    try:
        import PySide6  # noqa: F401
    except ImportError:
        print("The desktop GUI needs PySide6, which isn't installed.")
        print("Install it with:  pip install \"creator-forge[gui]\"")
        print("Then run:  forge gui")
        raise SystemExit(2)
    from forge.config import load_config
    from forge.gui.app import run
    config = load_config(config_path)
    return run(config)
