#!/usr/bin/env bash
# Assemble the goop-launcher .deb from the repo + a pre-built Wine tarball.
#
# The Wine tarball is produced by scripts/build-wine.sh + package-wine.sh in a
# separate "runtime-wine-11.9" release. This keeps the .deb build itself fast
# (no 30-minute Wine compile on every release) and lets us re-tag the deb
# without rebuilding Wine.
#
# Usage: scripts/build-deb.sh --wine-tarball FILE [--version V] [--out DIR]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

GOOP_ROOT="$(goop_root)"
VERSION="${GOOP_DEB_VERSION:-0.1.0}"
WINE_TARBALL=""
OUT_DIR="${GOOP_ROOT}/dist"
ARCH="amd64"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wine-tarball) WINE_TARBALL="$2"; shift 2;;
        --version) VERSION="$2"; shift 2;;
        --out) OUT_DIR="$2"; shift 2;;
        *) die "unknown arg: $1";;
    esac
done

[[ -n "$WINE_TARBALL" ]] || die "--wine-tarball is required (point at wine-11.9-goop-x86_64.tar.xz)"
[[ -f "$WINE_TARBALL" ]] || die "tarball not found: $WINE_TARBALL"

require_cmd dpkg-deb install

PKG_NAME="goop-launcher"
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

# ── Build the filesystem layout ──────────────────────────────────────────────
info "Staging package tree for ${PKG_NAME}_${VERSION}_${ARCH}…"
mkdir -p "${STAGING}/DEBIAN"
mkdir -p "${STAGING}/usr/bin"
mkdir -p "${STAGING}/usr/lib/${PKG_NAME}"
mkdir -p "${STAGING}/usr/share/applications"
mkdir -p "${STAGING}/usr/share/icons/hicolor/scalable/apps"
mkdir -p "${STAGING}/opt/goop/scripts"

# Python package.
cp -a "${GOOP_ROOT}/launcher/goop_launcher" "${STAGING}/usr/lib/${PKG_NAME}/"

# Shell scripts.
cp -a "${GOOP_ROOT}/scripts/"* "${STAGING}/opt/goop/scripts/"

# Wine 11.9 tree (from the release tarball).
info "Extracting Wine tarball into /opt/goop/wine-11.9…"
mkdir -p "${STAGING}/opt/goop/wine-11.9"
tar -xJf "$WINE_TARBALL" -C "${STAGING}/opt/goop" --strip-components=1
[[ -x "${STAGING}/opt/goop/wine-11.9/bin/wine64" ]] \
    || die "wine64 missing after extract — tarball layout wrong"

# Desktop entry + icon + launcher wrapper.
cp "${GOOP_ROOT}/package/goop.desktop" "${STAGING}/usr/share/applications/"
cp "${GOOP_ROOT}/package/assets/icons/goop.svg" \
   "${STAGING}/usr/share/icons/hicolor/scalable/apps/goop.svg"
cp "${GOOP_ROOT}/package/goop-launcher.sh" "${STAGING}/usr/bin/goop"
chmod 0755 "${STAGING}/usr/bin/goop"

# ── DEBIAN/control ───────────────────────────────────────────────────────────
# Installed-Size is in KiB; estimate from the staging tree.
INSTALLED_KIB="$(du -sk "${STAGING}" | awk '{print $1}')"
cat > "${STAGING}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: games
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_KIB}
Depends: python3, python3-gi, gir1.2-gtk-3.0, vulkan-tools, pciutils, curl
Recommends: nvidia-driver-535 (>= 535) | nvidia-driver-550 (>= 550)
Suggests: winetricks
Conflicts: vinegar, grapejuice
Maintainer: Alex Mondello <aaf2tbz@users.noreply.github.com>
Description: tiny Wine 11.9 launcher for Roblox on Linux Mint Cinnamon
 Goop Launcher stages a self-contained Wine 11.9 build with DXVK, then runs
 the official Roblox client under it. Targets NVIDIA GPUs (RTX 3060 Ti) with
 Vulkan. The launcher is a small GTK3 front-end that diagnoses the system,
 stages Roblox from roblox.com at first run, and launches it.
 .
 Roblox binaries are NOT redistributed; they are fetched at install/run time
 from the official Roblox CDN.
EOF

# ── DEBIAN/postinst ──────────────────────────────────────────────────────────
install -m 0755 "${GOOP_ROOT}/package/postinst" "${STAGING}/DEBIAN/postinst"
install -m 0755 "${GOOP_ROOT}/package/prerm" "${STAGING}/DEBIAN/prerm"

# ── Build the .deb ───────────────────────────────────────────────────────────
mkdir -p "$OUT_DIR"
DEB="${OUT_DIR}/${PKG_NAME}_${VERSION}_${ARCH}.deb"
info "Building ${DEB}…"
dpkg-deb --build --root-owner-group "$STAGING" "$DEB"

# Lintian is optional; only run if present (CI installs it).
if command -v lintian >/dev/null 2>&1; then
    info "Running lintian…"
    lintian --no-tag-display-limit "$DEB" || warn "lintian reported issues (non-fatal)"
fi

SIZE="$(du -h "$DEB" | awk '{print $1}')"
ok "Built ${DEB} (${SIZE})"
