#!/usr/bin/env bash
# Download and stage DXVK into the Goop Wine prefix.
#
# DXVK translates D3D9/10/11 → Vulkan. For an RTX 3060 Ti this is the entire
# point: Roblox's renderer goes through DXVK onto native Vulkan, which the
# proprietary NVIDIA driver exposes with full 1.3 support.
#
# We download the pinned DXVK tarball (see config.py) and copy the x64 DLLs
# into the prefix's windows/system32. The WINEDLLOVERRIDES env var (set in
# config.py) turns them native.
#
# Usage: scripts/stage-dxvk.sh [--prefix DIR]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

DXVK_VERSION="${GOOP_DXVK_VERSION:-2.6.1}"
WINEPREFIX_DIR="${GOOP_WINEPREFIX_DIR:-${HOME}/.local/share/goop/prefix}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version) DXVK_VERSION="$2"; shift 2;;
        --prefix) WINEPREFIX_DIR="$2"; shift 2;;
        *) die "unknown arg: $1";;
    esac
done

require_linux

SYSTEM32="${WINEPREFIX_DIR}/drive_c/windows/system32"
[[ -d "$SYSTEM32" ]] || die "Wine prefix system32 not found: ${SYSTEM32}\nRun goop-setup (which calls wineboot) first."

URL="https://github.com/doitsujin/dxvk/releases/download/v${DXVK_VERSION}/dxvk-${DXVK_VERSION}.tar.gz"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

TARBALL="${WORKDIR}/dxvk.tar.gz"
info "Downloading DXVK v${DXVK_VERSION}…"
goop_fetch "$URL" "$TARBALL"

info "Extracting DXVK…"
tar -xzf "$TARBALL" -C "$WORKDIR"
DXVK_ROOT="${WORKDIR}/dxvk-${DXVK_VERSION}"
[[ -d "${DXVK_ROOT}/x64" ]] || die "DXVK tarball layout unexpected (no x64/ dir)"

DLLS=(d3d9.dll d3d10core.dll d3d11.dll dxgi.dll)
info "Staging x64 DXVK DLLs into ${SYSTEM32}…"
for dll in "${DLLS[@]}"; do
    src="${DXVK_ROOT}/x64/${dll}"
    [[ -f "$src" ]] || die "DXVK tarball missing ${dll}"
    install -m 0644 "$src" "${SYSTEM32}/${dll}"
    ok "staged ${dll}"
done

ok "DXVK v${DXVK_VERSION} staged. WINEDLLOVERRIDES will make them native at launch."
