#!/usr/bin/env bash
# Tar the built Wine 11.9 tree into a release tarball.
#
# Produces wine-11.9-goop-x86_64.tar.xz in the dist dir. This is what the
# release workflow uploads as a GitHub release asset, and what build-deb.sh
# later downloads to assemble the .deb.
#
# Usage: scripts/package-wine.sh [--prefix DIR] [--out FILE]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

GOOP_WINE_VERSION="${GOOP_WINE_VERSION:-11.9}"
GOOP_WINE_PREFIX="${GOOP_WINE_PREFIX:-/opt/goop/wine-11.9}"
OUT="${GOOP_WINE_TARBALL:-dist/wine-${GOOP_WINE_VERSION}-goop-x86_64.tar.xz}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prefix) GOOP_WINE_PREFIX="$2"; shift 2;;
        --out) OUT="$2"; shift 2;;
        *) die "unknown arg: $1";;
    esac
done

[[ -d "$GOOP_WINE_PREFIX" ]] || die "Wine prefix not found: $GOOP_WINE_PREFIX"
[[ -x "${GOOP_WINE_PREFIX}/bin/wine" ]] || die "wine not found in prefix"

require_cmd tar xz

mkdir -p "$(dirname "$OUT")"

# The tarball stores a top-level wine-11.9/ dir so it extracts cleanly anywhere.
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT
TARGET_NAME="wine-${GOOP_WINE_VERSION}"
cp -a "$GOOP_WINE_PREFIX" "${STAGING}/${TARGET_NAME}"

# Record the version the tarball was built from, for verification on extract.
"${GOOP_WINE_PREFIX}/bin/wine" --version > "${STAGING}/${TARGET_NAME}/GOOP-WINE-VERSION.txt"

info "Creating ${OUT}…"
tar -C "$STAGING" -cJf "$OUT" "${TARGET_NAME}"

# Emit a sha256 next to it for downstream verification.
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$OUT" > "${OUT}.sha256"
else
    shasum -a 256 "$OUT" > "${OUT}.sha256"
fi

SIZE="$(du -h "$OUT" | awk '{print $1}')"
ok "Packaged ${OUT} (${SIZE})"
info "Publish this to a GitHub release tagged 'runtime-wine-${GOOP_WINE_VERSION}'."
