#!/bin/bash
# /usr/bin/goop — thin wrapper that runs the staged Python launcher.
# The package ships goop_launcher under /usr/lib/goop-launcher/.
set -e
export PYTHONPATH="/usr/lib/goop-launcher:${PYTHONPATH:-}"
exec python3 -m goop_launcher "$@"
