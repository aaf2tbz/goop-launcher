"""Goop Launcher — a tiny Wine 11.9 launcher for Roblox on Linux.

The package is split so that the GUI layer (``app.py``) is the *only* module
that imports PyGObject. Everything else (``config``, ``checks``, ``wine``,
``roblox``) is importable headless, which is what makes the test suite runnable
in CI without a display server.
"""

from __future__ import annotations

__all__ = ["__version__", "GOOP_APP_NAME"]

__version__ = "0.1.0"
GOOP_APP_NAME = "Goop Launcher"
