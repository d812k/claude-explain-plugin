# Proposal 0001: Python runtime, shell wrappers, registry format, manifest

Status: accepted on 2026-09-21. The design plan (`explain-selection-plugin-plan.md`) fixes
route B, inbox-socket injection. This proposal records how that design is realised under
the rules in `AGENTS.md`, which mandate a typed Python implementation rather than the bash
scripts sketched in the plan.

## 1. Context

- The plan specifies bash 3.2 scripts using `jq` and `nc`. `AGENTS.md` mandates Python 3.12,
  pydantic at the boundaries and the stdlib `socket` module. The plan's scripts are therefore
  specifications; the deliverable is the Python package plus thin wrappers.
- On the target Mac, `python3` is Homebrew-only. Runtime paths must be fast: the hook has a
  5 second budget and the hotkey path should feel instant. The user asked to move as much
  work as possible into the install step.
- The development machine is Linux aarch64. Verified there on 2026-09-21 against Claude
  Code 2.1.278: the inbox socket lives at `$XDG_RUNTIME_DIR/cc-socks/<pid>.sock` with mode
  0600 in a 0700 directory; `CLAUDE_CODE_MESSAGING_SOCKET` and `CLAUDE_CODE_MESSAGING_TOKEN`
  are exported to Bash commands; `claude agents --json` emits `pid`, `cwd`, `kind`,
  `startedAt`, `sessionId`, `name`, `status`; the parent pid of a Bash command equals the pid
  in the socket filename and in the agents list; `CwdChanged` exists as a hook event in the
  binary; a posted message is delivered between tool calls; the server sends no
  acknowledgement and does not close the connection after delivery.

## 2. Decisions

### 2.1 Runtime: install does the heavy work, wrappers only exec

- The install skill ensures `uv` is present (Homebrew first, official installer second),
  creates a venv at `~/.claude/explain-selection/venv` with a uv-managed Python 3.12,
  installs the plugin package from `${CLAUDE_PLUGIN_ROOT}` into that venv, and compiles
  bytecode. It re-runs on plugin update; `doctor` compares the installed package version
  with `plugin.json`.
- Hooks and the hotkey never invoke `uv`, never sync, never touch the network.
- Development fallback: if the install venv is missing, wrappers try `<plugin root>/.venv/bin/python`,
  so `claude --plugin-dir .` works from a checkout after `uv sync`.

### 2.2 Wrappers: POSIX sh, no fixed shell

- Every executable under `bin/` is `#!/bin/sh` with no bashisms or zshisms. The user's
  interactive shell is irrelevant to hooks and the hotkey.
- Interpreter resolution order: `$EXPLAIN_SELECTION_PYTHON` if set, then
  `$HOME/.claude/explain-selection/venv/bin/python`, then `<plugin root>/.venv/bin/python`.
  The wrapper then `exec`s `python -m explain_selection.entrypoints.<command> "$@"`.
- If no interpreter is found, hook wrappers exit 0 silently so a session never breaks; the
  hotkey wrapper shows a notification instead.
- Shell-specific work (shell rc edits, PATH lines) lives only in the install skill, detected
  from `$SHELL`, zsh first and bash next. Terminal emulators (iTerm2, Terminal.app, Ghostty)
  are handled on the capture side and are not shells.

### 2.3 Hooks

- Events: `SessionStart`, `CwdChanged`, `SessionEnd`, each with `timeout: 5`.
- Command form: string form with the plugin root quoted, for example
  `"\"${CLAUDE_PLUGIN_ROOT}/bin/explain-selection-register\""`. The array form is not
  verified in the docs and is not used.
- Hooks write nothing to stdout. Diagnostics go to a log file under `~/.claude/explain-selection/`.

### 2.4 Registry file format, version 1

- Directory `~/.claude/explain-selection/sessions/`, mode 0700. One file per session named
  `<pid>.json`, mode 0600, written atomically (temp file in the same directory, then rename).
- `pid` is the Claude Code process pid, taken from the basename of the socket path. No
  process-tree walk is needed to find it; `ps` is used only to learn the tty.
- Fields:
  - `version`: integer, 1
  - `sessionId`: string
  - `pid`: integer
  - `cwd`: string
  - `tty`: string or null (for example `ttys005` or `pts/2`)
  - `name`: string or null
  - `socket`: string, the inbox socket path
  - `token`: string, the per-session inbox token
  - `tmux`: string or null, the value of `$TMUX`
  - `tmuxPane`: string or null, the value of `$TMUX_PANE`
  - `registeredAt`: integer, epoch milliseconds from an injected clock
- Readers ignore unknown fields and skip files that fail validation, logging the filename
  only. Stale entries are pruned when their pid is not in `claude agents --json`.
- The token is a secret. It never appears in logs, test fixtures or committed files.

### 2.5 Plugin manifest

- `name` `explain-selection`, `version` kept equal to `pyproject.toml`, `description`, and
  `hooks` pointing at `./hooks/hooks.json`. Skills load from the default `skills/` directory.
- No `userConfig` in 0.1.0. The plan's `mode`, `auto_submit` and `btw` options describe
  mode C, which is not built, and the hotkey runs outside Claude Code where `userConfig` is
  not visible. All settings live in `~/.claude/explain-selection/config.env`.

### 2.6 Configuration

- One `pydantic-settings` `Settings` object built in each `main()` from `config.env` and the
  process environment with the prefix `EXPLAIN_SELECTION_`. Nothing else reads the environment.
- Initial keys: `max_chars` (default 200000), `long_selection` (`truncate` or `tempfile`, for
  mode A), `prompt_template` (path, default the shipped template), `remember_target_minutes`
  (default 10), `home` (default `~/.claude/explain-selection`).

### 2.7 Socket client

- Build both JSON lines first, connect with a 2 second timeout, send them in one call, close.
  Do not wait for a reply: the server sends none and keeps the connection open.

### 2.8 Prompt template

- `templates/explain-prompt.txt` with a `{text}` placeholder. It inlines the explain framing,
  asks for a concise answer and a return to the previous task, and ends with the plan's
  trailer stating that the message relays the user's own request.

## 3. Consequences

- The plan's `scripts/` directory does not exist. Its contents map to the Python package:
  `register-session.sh` and `unregister-session.sh` become the `register` and `unregister`
  entrypoints; `find-target.sh` becomes pure target ranking in `domain` plus adapters;
  `deliver-inject.sh` and `deliver-newwindow.sh` become the socket and deep-link adapters;
  `lib.sh` disappears.
- A `make validate` target runs `claude plugin validate . --strict`. It is not part of
  `make check` because it needs the `claude` binary; it runs in `make test-all`.
