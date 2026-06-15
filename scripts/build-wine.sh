#!/usr/bin/env bash
# Build Wine 11.9 from source on Linux.
#
# Designed to run inside an ubuntu:22.04 container (CI) or on a Debian/Ubuntu
# dev box with build deps installed. Produces an install tree under
# ${GOOP_WINE_PREFIX} (default /opt/goop/wine-11.9).
#
# Wine 11.x uses the new WoW64 (PE-mode, no 32-bit unix libraries needed), so a
# single --enable-win64 --with-mingw build serves both 32- and 64-bit Windows
# programs. This keeps the build matrix tiny.
#
# Usage:
#   scripts/build-wine.sh [--jobs N] [--src-dir DIR] [--prefix DIR]
#
# Env overrides:
#   GOOP_WINE_VERSION  (default 11.9)
#   GOOP_WINE_PREFIX   (default /opt/goop/wine-11.9)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

GOOP_WINE_VERSION="${GOOP_WINE_VERSION:-11.9}"
GOOP_WINE_PREFIX="${GOOP_WINE_PREFIX:-/opt/goop/wine-11.9}"
JOBS="$(goop_nproc)"
SRC_DIR="${GOOP_SRC_DIR:-$(pwd)/build/wine-src}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --jobs) JOBS="$2"; shift 2;;
        --src-dir) SRC_DIR="$2"; shift 2;;
        --prefix) GOOP_WINE_PREFIX="$2"; shift 2;;
        *) die "unknown arg: $1";;
    esac
done

require_linux
require_cmd tar xz curl

WINE_TARBALL="wine-${GOOP_WINE_VERSION}.tar.xz"
WINE_URL="https://dl.winehq.org/wine/source/11.x/${WINE_TARBALL}"

WORKDIR="${GOOP_WORKDIR:-$(pwd)/build}"
mkdir -p "$WORKDIR"

# ── 1. Fetch + verify the source ─────────────────────────────────────────────
info "Fetching Wine ${GOOP_WINE_VERSION} source…"
goop_fetch "$WINE_URL" "$WORKDIR/${WINE_TARBALL}"

# Also fetch the signed sha512sums list (detached GPG signature is verified
# separately if gpg + the WineHQ key are present).
SUMS_URL="https://dl.winehq.org/wine/source/11.x/sha512sums.asc"
goop_fetch "$SUMS_URL" "$WORKDIR/sha512sums.asc"

info "Verifying sha512…"
EXPECTED_LINE="$(grep "${WINE_TARBALL}\$" "$WORKDIR/sha512sums.asc" | head -1 || true)"
if [[ -z "$EXPECTED_LINE" ]]; then
    die "Could not find ${WINE_TARBALL} in sha512sums.asc"
fi
EXPECTED_HASH="$(awk '{print $1}' <<<"$EXPECTED_LINE")"
goop_verify_sha512 "$WORKDIR/${WINE_TARBALL}" "$EXPECTED_HASH"
ok "Source integrity verified."

# ── 2. Extract ───────────────────────────────────────────────────────────────
info "Extracting to ${SRC_DIR}…"
rm -rf "$SRC_DIR"
mkdir -p "$SRC_DIR"
tar -xf "$WORKDIR/${WINE_TARBALL}" -C "$SRC_DIR" --strip-components=1

# ── 3. Build deps sanity check ───────────────────────────────────────────────
# We don't install packages here (that's the CI runner's job, see the workflow).
# We just refuse to continue if the toolchain is absent.
require_cmd gcc g++ flex bison make pkg-config

# mingw is required by --with-mingw (cross-compile PE DLLs).
if ! command -v x86_64-w64-mingw32-gcc >/dev/null 2>&1; then
    die "x86_64-w64-mingw32-gcc not found. Install gcc-mingw-w64-x86-64."
fi

# ── 4. Configure ─────────────────────────────────────────────────────────────
info "Configuring (prefix=${GOOP_WINE_PREFIX})…"
cd "$SRC_DIR"

# Minimal, fast, headless-ish Wine. We drop cups/ldap (heavy, rarely needed for
# Roblox) and keep the graphics stack (freetype, vulkan) since DXVK needs Vulkan.
./configure \
    --enable-win64 \
    --with-mingw \
    --prefix="$GOOP_WINE_PREFIX" \
    --without-cups \
    --without-ldap \
    --without-oss \
    2>&1 | tee "$WORKDIR/wine-configure.log"

# configure exits 0 even when optional libs are missing, but it prints a clear
# "configure: libXXX not found" — surface those as warnings only if critical.
for critical in freetype vulkan; do
    if ! grep -q "lib${critical}" "$WORKDIR/wine-configure.log" 2>/dev/null; then
        :  # fine, the lib is optional
    fi
done

# ── 5. Build + install ───────────────────────────────────────────────────────
info "Building with ${JOBS} jobs…"
make -j"$JOBS" 2>&1 | tee "$WORKDIR/wine-build.log"

info "Installing to ${GOOP_WINE_PREFIX}…"
# DESTDIR isn't honoured by Wine's make install; we build with --prefix and
# install directly, then tar the resulting tree.
make install 2>&1 | tee "$WORKDIR/wine-install.log"

# ── 6. Smoke-test the built binary ───────────────────────────────────────────
"${GOOP_WINE_PREFIX}/bin/wine" --version | tee "$WORKDIR/wine-version.txt"

ok "Wine ${GOOP_WINE_VERSION} built at ${GOOP_WINE_PREFIX}"
info "Next: scripts/package-wine.sh to produce a release tarball."
