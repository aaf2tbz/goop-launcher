"""Roblox staging and launch.

We never redistribute Roblox. At install/first-run time we fetch the official
``RobloxPlayerLauncher.exe`` from roblox.com and stage it into the Wine prefix.
Launch re-invokes the staged RobloxPlayerLauncher inside our Wine 11.9 prefix.

Roblox's Hyperion anti-cheat periodically changes its Wine compatibility story.
This module does not overclaim: it stages the official client and surfaces real
exit codes. If Roblox refuses to run under a given Wine build, that's a Roblox
decision and must be reported to the user honestly.
"""

from __future__ import annotations

import shutil
import subprocess
import urllib.request
from pathlib import Path

from . import config
from . import wine


class RobloxError(RuntimeError):
    pass


def download_launcher(dest_dir: Path | None = None) -> Path:
    """Fetch RobloxPlayerLauncher.exe from the official Roblox CDN."""
    dest = dest_dir or config.DOWNLOADS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / "RobloxPlayerLauncher.exe"

    req = urllib.request.Request(
        config.ROBLOX_PLAYER_LAUNCHER_URL,
        headers={"User-Agent": config.ROBLOX_SETUP_USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, \
                open(target, "wb") as fh:
            shutil.copyfileobj(resp, fh)
    except Exception as exc:  # noqa: BLE001
        raise RobloxError(
            f"Could not download Roblox launcher from "
            f"{config.ROBLOX_PLAYER_LAUNCHER_URL}: {exc}"
        ) from exc

    if target.stat().st_size < 1024 * 1024:
        raise RobloxError(
            f"Roblox launcher is suspiciously small "
            f"({target.stat().st_size} bytes); refusing to stage it."
        )
    return target


def stage(launcher_exe: Path) -> Path:
    """Copy the official launcher into the prefix's LocalAppData/Roblox."""
    config.ROBLOX_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.ROBLOX_INSTALL_DIR / launcher_exe.name
    shutil.copy2(launcher_exe, dest)
    return dest


def launch() -> int:
    """Run the staged Roblox launcher under our Wine 11.9 prefix.

    Returns the wine exit code. The GUI watches this to report real failures.
    """
    launcher = config.ROBLOX_INSTALL_DIR / "RobloxPlayerLauncher.exe"
    if not launcher.exists():
        raise RobloxError(
            "Roblox is not staged. Run Download+Install from the launcher first."
        )

    wine_bin = wine.find_wine()
    env = wine.wine_env()
    # Roblox benefits from a virtual desktop on some compositors; leave it off
    # by default but let the user set GOOP_VIRTUAL_DESKTOP=1920x1080.
    vd = env.get("GOOP_VIRTUAL_DESKTOP")
    cmd = [str(wine_bin)]
    if vd:
        cmd += ["explorer", f"/desktop=Roblox,{vd}"]
    cmd.append(str(launcher))

    # We do NOT capture output for launch — the game owns the terminal/window.
    proc = subprocess.run(cmd, env=env, check=False)
    return proc.returncode
