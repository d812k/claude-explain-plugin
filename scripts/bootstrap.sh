#!/bin/sh
# One-time setup run by the install skill: prepare the runtime venv, then hand over to the
# Python installer. Usage: scripts/bootstrap.sh [--shortcut KEY] [--dry-run]
# The hotkey path never runs this; it only execs the shim this installs.
# With --dry-run nothing is created: an existing venv runs the installer's own dry run,
# otherwise the planned steps are printed and the script exits 0.
set -eu
here=$(cd "$(dirname "$0")" && pwd -P)
root=$(dirname "$here")
home="${EXPLAIN_SELECTION_HOME:-$HOME/.claude/explain-selection}"
dry_run=no
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ]; then
    dry_run=yes
  fi
done
if [ "$dry_run" = yes ] && [ ! -x "$home/venv/bin/python" ]; then
  echo "[planned] venv: would create $home/venv with uv venv --python 3.12"
  echo "[planned] package: would install $root into the venv"
  echo "[planned] install: would run explain-selection install --dry-run"
  exit 0
fi
if [ "$dry_run" = no ]; then
  if ! command -v uv >/dev/null 2>&1; then
    echo "explain-selection: uv is required; install it with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
  fi
  mkdir -p "$home"
  chmod 700 "$home"
  if [ ! -x "$home/venv/bin/python" ]; then
    uv venv --python 3.12 "$home/venv"
  fi
  uv pip install --python "$home/venv/bin/python" --quiet "$root"
fi
exec "$home/venv/bin/python" -m explain_selection.entrypoints.cli install --plugin-root "$root" "$@"
