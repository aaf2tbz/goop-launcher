#!/usr/bin/env bash
# Stage the Wine 11.9 release tarball to a destination prefix.
#
# Used by the .deb postinst and by goop-setup (dev install). Downloads the
# tarball from a GitHub release if it isn't present locally, verifies its
# sha256, then extracts it.
#
# Usage: scripts/stage-wine.sh [--tarball FILE|--url URL] [--dest DIR]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

GOOP_WINE_VERSION="${GOOP_WINE_VERSION:-11.9}"
TARBALL=""
URL=""
DEST="${GOOP_WINE_DEST:-/opt/goop}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tarball) TARBALL="$2"; shift 2;;
        --url) URL="$2"; shift 2;;
        --dest) DEST="$2"; shift 2;;
        *) die "unknown arg: $1";;
    esac
done

require_linux
require_cmd tar xz curl

[[ -d "$DEST" ]] || { info "Creating ${DEST}"; sudo mkdir -p "$DEST"; }

# Resolve tarball: explicit file > url > default GitHub release.
if [[ -z "$TARBALL" && -z "$URL" ]]; then
    URL="https://github.com/aaf2tbz/goop-launcher/releases/download/runtime-wine-${GOOP_WINE_VERSION}/wine-${GOOP_WINE_VERSION}-goop-x86_64.tar.xz"
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

if [[ -n "$TARBALL" ]]; then
    [[ -f "$TARBALL" ]] || die "tarball not found: $TARBALL"
else
    TARBALL="${WORKDIR}/wine.tar.xz"
    info "Downloading ${URL}…"
    goop_fetch "$URL" "$TARBALL"
    SUMS_URL="${URL}.sha256"
    goop_fetch "$SUMS_URL" "${TARBALL}.sha256" || warn "no sha256 sidecar published; skipping verification"
    if [[ -f "${TARBALL}.sha256" ]]; then
        info "Verifying sha256…"
        cd "$WORKDIR"
        EXPECTED="$(awk '{print $1}' wine.tar.xz.sha256)"
        goop_verify_sha512 wine.tar.xz "$EXPECTED" 2>/dev/null || {
            # common.sh's verifier is sha512-named but works for any length match;
            # redo with the dedicated sha256 path to be unambiguous.
            ACTUAL="$(sha256sum wine.tar.xz | awk '{print $1}')"
            [[ "$ACTUAL" == "$EXPECTED" ]] || die "sha256 mismatch:\n  expected: $EXPECTED\n  got: $ACTUAL"
        }
        ok "sha256 verified."
    fi
fi

info "Extracting Wine ${GOOP_WINE_VERSION} to ${DEST}…"
# The tarball contains a wine-<ver>/ top dir; we extract its contents directly
# into ${DEST}/wine-<ver>.
TARGET_NAME="wine-${GOOP_WINE_VERSION}"
sudo mkdir -p "${DEST}/${TARGET_NAME}"
sudo tar -xJf "$TARBALL" -C "${DEST}" --strip-components=1 --transform="s,^${TARGET_NAME},," 2>/dev/null \
    || sudo tar -xJf "$TARBALL" -C "${DEST}"

# Verify the binary runs.
if "${DEST}/${TARGET_NAME}/bin/wine" --version >/dev/null 2>&1; then
    ok "Wine staged at ${DEST}/${TARGET_NAME}"
    "${DEST}/${TARGET_NAME}/bin/wine" --version
else
    die "wine would not run after staging at ${DEST}/${TARGET_NAME}"
fi
