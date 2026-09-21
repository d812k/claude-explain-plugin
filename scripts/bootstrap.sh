#!/bin/sh
# One-time setup run by the install skill: prepare the runtime venv, then hand over to the
# Python installer. Usage: scripts/bootstrap.sh [--shortcut KEY] [--dry-run]
# The hotkey path never runs this; it only execs the shim this installs.
set -eu
here=$(cd "$(dirname "$0")" && pwd -P)
root=$(dirname "$here")
home="${EXPLAIN_SELECTION_HOME:-$HOME/.claude/explain-selection}"
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
exec "$home/venv/bin/python" -m explain_selection.entrypoints.cli install --plugin-root "$root" "$@"
