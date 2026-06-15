#!/usr/bin/env bash
# Shared helpers for Goop Launcher shell scripts.
# Sourced by every script; never executed directly.
#
# Conventions:
#   set -euo pipefail is the caller's job (we set it here to be safe).
#   info/ok/warn/fail are the only logging primitives.
#   die() prints and exits 1; require_cmd() asserts a binary is present.

set -euo pipefail

GOOP_COLORS_TTY=0
if [[ -t 1 ]]; then GOOP_COLORS_TTY=1; fi

if [[ "$GOOP_COLORS_TTY" == "1" ]]; then
    C_RED=$'\033[0;31m'; C_GREEN=$'\033[0;32m'; C_YELLOW=$'\033[1;33m'
    C_CYAN=$'\033[0;36m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'; C_NC=$'\033[0m'
else
    C_RED=""; C_GREEN=""; C_YELLOW=""; C_CYAN=""; C_BOLD=""; C_DIM=""; C_NC=""
fi

info()  { printf '%s[goop]%s %s\n' "$C_CYAN" "$C_NC" "$*"; }
ok()    { printf '%s[ok]%s %s\n' "$C_GREEN" "$C_NC" "$*"; }
warn()  { printf '%s[warn]%s %s\n' "$C_YELLOW" "$C_NC" "$*" >&2; }
die()   { printf '%s[fail]%s %s\n' "$C_RED" "$C_NC" "$*" >&2; exit 1; }

require_cmd() {
    local missing=0
    for c in "$@"; do
        if ! command -v "$c" >/dev/null 2>&1; then
            warn "missing required command: $c"
            missing=1
        fi
    done
    [[ "$missing" -eq 0 ]] || die "Required commands are missing (see above). Install them and retry."
}

require_linux() {
    [[ "$(uname -s)" == "Linux" ]] || die "This script must run on Linux (got $(uname -s))."
}

# Resolve the repo root (parent of scripts/).
goop_root() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
    (cd "$script_dir/.." && pwd)
}

# nproc with a fallback for macOS/BSD.
goop_nproc() {
    if command -v nproc >/dev/null 2>&1; then nproc
    elif [[ "$(uname -s)" == "Darwin" ]]; then sysctl -n hw.ncpu
    else echo 2; fi
}

# Download a URL with curl (preferred) or wget, streaming to a file.
# Usage: goop_fetch <url> <dest>
goop_fetch() {
    local url="$1" dest="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 3 --connect-timeout 30 -o "$dest" "$url"
    elif command -v wget >/dev/null 2>&1; then
        wget -q --tries=3 --timeout=30 -O "$dest" "$url"
    else
        die "Need curl or wget to download $url"
    fi
}

# Verify a sha512sum line for one file.
# Usage: goop_verify_sha512 <file> <expected_sha512_hex>
goop_verify_sha512() {
    local file="$1" expected="$2" actual
    [[ -f "$file" ]] || die "file not found: $file"
    if command -v sha512sum >/dev/null 2>&1; then
        actual="$(sha512sum "$file" | awk '{print $1}')"
    else  # macOS shasum
        actual="$(shasum -a 512 "$file" | awk '{print $1}')"
    fi
    [[ "$actual" == "$expected" ]] || die "sha512 mismatch for $file\n  expected: $expected\n  got:      $actual"
}
