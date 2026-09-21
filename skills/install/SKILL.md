---
name: install
description: Install the explain-selection hotkey on this Mac: runtime venv, Services entry, shortcut and config
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash
---

Install the explain-selection hotkey on this Mac: runtime venv, Services entry, keyboard shortcut, and configuration.

1. Check if `uv` is present with `command -v uv`. If it is not found, show the user the install command `curl -LsSf https://astral.sh/uv/install.sh | sh` and ask before running it.

2. Run the bootstrap script: `"${CLAUDE_PLUGIN_ROOT}/scripts/bootstrap.sh"`. Show the step lines as they appear. Each line has the form `[done|skipped|planned|failed] name: detail` for the steps `home`, `config`, `prompt`, `shim`, `service`, `shortcut`.

3. If any step is marked `failed`, explain the fix to the user:
   - `shortcut` step: open System Settings > Keyboard > Keyboard Shortcuts > Services > Text > Explain selection, then set the shortcut manually.
   - Other steps: the detail text in the step output describes what went wrong. Relay it to the user.

4. Tell the user to relaunch their terminal apps (iTerm2, Terminal, Ghostty) so the Services menu picks up the new entry. The first time they press the hotkey with several Claude Code sessions open, macOS will ask to allow automation of iTerm2 or Terminal. Click Allow.

5. Ask the user to select text in a terminal, press Command-Option-E, and expect the explanation to arrive in the session (or open a new window when no session is running).

6. Suggest running `/explain-selection:doctor` to verify the installation.

Notes:
- The shortcut can be changed with `--shortcut KEY`. Format: `@` for Command, `~` for Option, `^` for Control, `$` for Shift, then the letter. For example, `--shortcut '@~x'` sets Command-Option-X.
- Re-running the install is safe and idempotent. It will update the venv, refresh the shim, and verify the Services entry and shortcut.
- `--dry-run` shows the planned steps without making changes; when the runtime venv does not exist yet, bootstrap prints what it would create and stops, since the dry run of the install step needs the venv's Python.
