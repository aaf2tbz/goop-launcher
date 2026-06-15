#!/usr/bin/env bash
# goop-setup — the user-facing installer for Goop Launcher.
#
# Run once after installing the .deb (the deb postinst calls this too). It:
#   1. Verifies the system is fit (guards mirror the Python checks).
#   2. Stages Wine 11.9 to /opt/goop/wine-11.9 (if not already staged by deb).
#   3. Initialises the Wine prefix (~/.local/share/goop/prefix).
#   4. Stages DXVK DLLs into the prefix.
#
# It does NOT download Roblox — that happens from the GUI/CLI at first run, so
# the user always gets the current official client.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

WINE_PREFIX="/opt/goop/wine-11.9"
USER_DATA_DIR="${GOOP_DATA_DIR:-${HOME}/.local/share/goop}"
USER_PREFIX="${USER_DATA_DIR}/prefix"

require_linux

echo "${C_BOLD}${C_CYAN}"
cat <<'BANNER'
   ____ _   _ ___ _   _
  / ___| | | / __| | | |
 | |  _| |_| \__ \ |_| |
 | |_| |  _  |___)  _  |
  \____|_| |_|____|_| |_|   Wine 11.9 + DXVK launcher for Roblox
BANNER
echo "${C_NC}"

# ── 1. Guards (mirror launcher/goop_launcher/checks.py) ─────────────────────
ARCH="$(uname -m)"
[[ "$ARCH" == "x86_64" ]] || die "Goop needs x86_64 (found ${ARCH})."

# Disk space: need ~5 GB for the prefix + Roblox.
mkdir -p "$USER_DATA_DIR"
FREE_MB="$(df -m "$USER_DATA_DIR" | awk 'NR==2 {print $4}')"
[[ "$FREE_MB" -ge 5000 ]] || die "Only ${FREE_MB} MB free at ${USER_DATA_DIR}; need >=5000 MB."

# Vulkan tools — hard requirement for DXVK.
require_cmd vulkaninfo lspci

if ! vulkaninfo --summary >/dev/null 2>&1; then
    die "vulkaninfo could not enumerate a Vulkan device. Install the NVIDIA driver + vulkan-tools."
fi
ok "Vulkan is available."

# nvidia-smi is strongly expected (we target the 3060 Ti).
if command -v nvidia-smi >/dev/null 2>&1; then
    DRV="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)"
    ok "NVIDIA driver ${DRV}"
else
    warn "nvidia-smi not found. Goop targets NVIDIA; proceeding anyway."
fi

# ── 2. Wine 11.9 staging ────────────────────────────────────────────────────
if [[ -x "${WINE_PREFIX}/bin/wine64" ]]; then
    VER="$("${WINE_PREFIX}/bin/wine64" --version)"
    ok "Wine already staged: ${VER}"
else
    info "Wine 11.9 not staged. (The .deb normally stages it to ${WINE_PREFIX}.)"
    if [[ "$EUID" -eq 0 ]]; then
        die "Run goop-setup as your normal user; the deb postinst handles /opt staging."
    fi
    info "Falling back to per-user staging at ${USER_DATA_DIR}/wine-11.9…"
    "${SCRIPT_DIR}/stage-wine.sh" --dest "${USER_DATA_DIR}" \
        || die "Failed to stage Wine 11.9."
    WINE_PREFIX="${USER_DATA_DIR}/wine-11.9"
fi

# ── 3. Initialise the Wine prefix ───────────────────────────────────────────
export WINEPREFIX="$USER_PREFIX"
export WINEARCH="win64"
export WINEESYNC=1
export WINEFSYNC=1
export PATH="${WINE_PREFIX}/bin:${PATH}"

mkdir -p "$USER_PREFIX"
if [[ -f "${USER_PREFIX}/system.reg" ]]; then
    ok "Wine prefix already initialised at ${USER_PREFIX}"
else
    info "Initialising Wine prefix (wineboot --init)…"
    wineboot --init
    wineserver -w || true
    ok "Prefix ready at ${USER_PREFIX}"
fi

# ── 4. Stage DXVK ───────────────────────────────────────────────────────────
SYSTEM32="${USER_PREFIX}/drive_c/windows/system32"
if [[ -f "${SYSTEM32}/d3d11.dll" && -f "${SYSTEM32}/dxgi.dll" ]]; then
    ok "DXVK already staged."
else
    "${SCRIPT_DIR}/stage-dxvk.sh" --prefix "$USER_PREFIX"
fi

# ── 5. Done ─────────────────────────────────────────────────────────────────
echo ""
ok "Goop Launcher is installed."
info "Launch it from your applications menu, or run:  goop"
info "First run will download Roblox from roblox.com and stage it."
