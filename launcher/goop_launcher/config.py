"""Version pins, URLs, and resolved paths for Goop Launcher.

All remote artifacts are pinned here so the shell scripts and the Python
launcher never disagree about what to fetch. Mirrors are tried in order.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Versions (pinned) ────────────────────────────────────────────────────────
GOOP_VERSION = "0.1.0"
WINE_VERSION = "11.9"
# DXVK translates D3D9/10/11 → Vulkan. Pinned release; RTX 3060 Ti loves Vulkan.
DXVK_VERSION = "2.6.1"
# Microsoft VC++ redistributable staging version (fetched from official MS CDN).
VCREDIST_VERSION = "14.40.33810.0"

# ── Remote artifact URLs ─────────────────────────────────────────────────────
# Wine 11.9 source + detached GPG signature + sha512sums (verified 2026-05-15).
WINE_SOURCE_URL = (
    f"https://dl.winehq.org/wine/source/11.x/wine-{WINE_VERSION}.tar.xz"
)
WINE_SOURCE_SIGN_URL = WINE_SOURCE_URL + ".sign"
WINE_SHA512SUMS_URL = "https://dl.winehq.org/wine/source/11.x/sha512sums.asc"

# DXVK release tarball from GitHub.
DXVK_URL = (
    f"https://github.com/doitsujin/dxvk/releases/download/v{DXVK_VERSION}/"
    f"dxvk-{DXVK_VERSION}.tar.gz"
)

# Roblox is fetched at runtime from the official setup domain.
# We never redistribute Roblox binaries — copyright belongs to Roblox Corp.
ROBLOX_PLAYER_LAUNCHER_URL = "https://roblox.com/download/client"
ROBLOX_SETUP_USER_AGENT = "GoopLauncher/" + GOOP_VERSION

# ── Resolved paths ───────────────────────────────────────────────────────────
# XDG-aware. Mint Cinnamon honours XDG_DATA_HOME / XDG_CONFIG_HOME.
def _xdg(env: str, fallback: str) -> Path:
    val = os.environ.get(env)
    return Path(val) if val else Path.home() / fallback

DATA_DIR = _xdg("XDG_DATA_HOME", ".local/share") / "goop"
CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config") / "goop"
CACHE_DIR = _xdg("XDG_CACHE_HOME", ".cache") / "goop"

# Staged Wine 11.9 tree (the deb installs a copy to /opt/goop/wine-11.9; the
# launcher prefers that, falling back to a per-user staging dir for dev).
SYSTEM_WINE_DIR = Path("/opt/goop/wine-11.9")
USER_WINE_DIR = DATA_DIR / "wine-11.9"

# The Wine prefix Roblox lives in.
PREFIX_DIR = DATA_DIR / "prefix"

# Staged Roblox assets live inside the prefix's drive_c.
ROBLOX_DRIVE_C = PREFIX_DIR / "drive_c" / "users" / os.environ.get("USER", "steamuser")
ROBLOX_INSTALL_DIR = ROBLOX_DRIVE_C / "AppData" / "Local" / "Roblox"

# Downloads/cache for installers.
DOWNLOADS_DIR = CACHE_DIR / "downloads"

# Wine prefix environment. RTX 3060 Ti wants DXVK + Vulkan.
WINE_ENV_BASE: dict[str, str] = {
    "WINEPREFIX": str(PREFIX_DIR),
    "WINEARCH": "win64",
    "WINEDLLOVERRIDES": "d3d9=native; d3d10core=native; d3d11=native; dxgi=native",
}

# ── Thresholds for the guards ────────────────────────────────────────────────
MIN_DISK_MB = 5000            # ~5 GB free for prefix + Roblox staging.
MIN_VULKAN_API_VERSION = (1, 3)  # DXVK 2.x wants Vulkan 1.3+.
SUPPORTED_ARCHES = ("x86_64",)
TARGET_GPU = "3060 Ti"        # advisory; we accept any recent NVIDIA dGPU.
TARGET_DRIVER_MIN = 535       # NVIDIA branch that ships Vulkan 1.3 fully.

# The exact Wine build we will run. Asserted at launch time.
EXPECTED_WINE_VERSION = "wine-" + WINE_VERSION
