"""Wine prefix management for Goop Launcher.

We avoid winetricks (it's a moving dependency and pulls wine-mono etc.). Instead
we initialise the prefix with explicit ``wineboot`` calls and drop DXVK DLLs in
by hand. This is the same approach Lutris takes for known-good configurations.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from . import config


class WineError(RuntimeError):
    pass


def find_wine() -> Path:
    """Locate the staged Wine 11.9 binary or raise.

    Wine 11.x (new WoW64, default since 9.0) installs a unified ``bin/wine``
    that serves both 32- and 64-bit. We prefer that, falling back to the
    legacy ``bin/wine64`` so the code stays tolerant of older system Wines.
    """
    for base in (config.SYSTEM_WINE_DIR, config.USER_WINE_DIR):
        for name in ("wine", "wine64"):
            candidate = base / "bin" / name
            if candidate.exists():
                return candidate
    raise WineError(
        "Wine 11.9 is not staged. Expected it at "
        f"{config.SYSTEM_WINE_DIR} or {config.USER_WINE_DIR}. "
        "Run `goop-setup` (or the .deb postinst) first."
    )


def wine_env(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = dict(os.environ)
    env.update(config.WINE_ENV_BASE)
    if extra:
        env.update(extra)
    return env


def _run(cmd: list[str], env: Optional[dict[str, str]] = None,
         timeout: int = 300) -> subprocess.CompletedProcess:
    """Run a wine command with our environment, fail loudly."""
    full_env = wine_env() if env is None else env
    proc = subprocess.run(cmd, env=full_env, capture_output=True, text=True,
                          timeout=timeout)
    if proc.returncode != 0:
        raise WineError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout: {proc.stdout[-2000:]}\nstderr: {proc.stderr[-2000:]}"
        )
    return proc


def init_prefix() -> Path:
    """Create and initialise the Wine prefix if missing.

    Idempotent: if the prefix already has system.reg we leave it alone.
    """
    prefix = config.PREFIX_DIR
    if (prefix / "system.reg").exists():
        return prefix

    prefix.mkdir(parents=True, exist_ok=True)
    wine = find_wine()

    # wineboot initialises the prefix without launching a GUI.
    _run([str(wine), "wineboot", "--init"])

    # Wait for the wineserver to settle so subsequent writes don't race.
    # wineserver lives next to wine in the same bin/ dir.
    wineserver = wine.parent / "wineserver"
    if wineserver.exists():
        _run([str(wineserver), "-w"], timeout=120)

    return prefix


def install_dxvk(dxvk_tarball: Path) -> None:
    """Stage DXVK DLLs into the prefix.

    DXVK ships d3d9.dll, d3d10core.dll, d3d11.dll, dxgi.dll for x64 (and x32
    for 32-bit prefixes, which we don't need under new-WoW64). We copy the x64
    builds into windows/system32 and let WINEDLLOVERRIDES turn them native.
    """
    if not dxvk_tarball.exists():
        raise WineError(f"DXVK tarball not found: {dxvk_tarball}")

    import tarfile
    system32 = config.PREFIX_DIR / "drive_c" / "windows" / "system32"
    system32.mkdir(parents=True, exist_ok=True)

    staged_dlls: list[Path] = []
    with tarfile.open(dxvk_tarball, "r:gz") as tar:
        # DXVK layout: dxvk-<ver>/x64/{d3d9,d3d10core,d3d11,dxgi}.dll
        for member in tar.getmembers():
            name = os.path.basename(member.name)
            if "/x64/" in member.name and name in {
                "d3d9.dll", "d3d10core.dll", "d3d11.dll", "dxgi.dll",
            }:
                # Extract to a temp then move into system32.
                f = tar.extractfile(member)
                if f is None:
                    continue
                dest = system32 / name
                dest.write_bytes(f.read())
                staged_dlls.append(dest)

    if len(staged_dlls) < 4:
        raise WineError(
            f"DXVK stage incomplete: only found {len(staged_dlls)} DLLs "
            f"({[p.name for p in staged_dlls]}). Expected 4."
        )


def verify_prefix() -> bool:
    """Sanity-check that the prefix has the minimum needed files."""
    prefix = config.PREFIX_DIR
    required = [
        prefix / "system.reg",
        prefix / "drive_c" / "windows" / "system32" / "d3d11.dll",
        prefix / "drive_c" / "windows" / "system32" / "dxgi.dll",
    ]
    return all(p.exists() for p in required)
