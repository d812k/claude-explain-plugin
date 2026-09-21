# explain-selection

A Claude Code plugin that delivers terminal selections into your running session. Select text in iTerm2, Terminal or Ghostty, press Command-Option-E, and the text arrives wrapped in the explain prompt.

## Requirements

- macOS (for the hotkey; the CLI and skills work on Linux)
- Claude Code with cross-session messaging (the per-session inbox socket)
- Python 3.12 (installed by the plugin)
- uv; the install skill shows the install command and asks before running it

## Install

1. Add the plugin marketplace: `/plugin marketplace add d812k/claude-explain-plugin`
2. Install the plugin: `/plugin install explain-selection@explain-selection`
3. Run the install skill: `/explain-selection:install`
4. Relaunch your terminal apps (iTerm2, Terminal, Ghostty) so the Services menu picks up the new entry
5. Run `/explain-selection:doctor` to verify the installation

The first time you press the hotkey with several sessions open, macOS will ask to allow automation of iTerm2 or Terminal. Click Allow.

The install step creates a Python 3.12 venv at `~/.claude/explain-selection/venv`, installs the package, copies the Automator Quick Action to `~/Library/Services`, assigns the keyboard shortcut through the `pbs` services database, and writes the configuration and prompt template.

## Usage

### Hotkey

Select text in a terminal and press Command-Option-E. The selection is delivered to Claude Code as a peer message wrapped in the explain prompt.

When exactly one interactive session is running, the selection goes there. When several sessions run, the plugin chooses the target with this ladder:

1. The session in the focused tmux pane
2. The session on the focused terminal tty (iTerm2 or Terminal, read through AppleScript)
3. The session picked in the chooser recently (remembered for a configurable number of minutes)
4. The only idle session
5. Otherwise a chooser dialog listing sessions idle first, then busy, then waiting

When no interactive session is running, a new Claude Code window opens with `/explain-selection:explain <text>` (at most 5000 characters of text) through the `claude-cli://` deep link.

A notification reports truncation, delivery to a busy session, and the new-window fallback. Selections longer than the configured maximum are truncated with a marker and the selected size is reported.

### Skills

- `/explain-selection:explain <text>` — Explain text pasted as the argument. Receiving end of the new-window fallback; also for manual use.
- `/explain-selection:send` — List sessions and send a message to another session.
- `/explain-selection:install` — Run the installation.
- `/explain-selection:doctor` — Check the installation, the live sessions and the inbox policy, and explain how to fix what is wrong.

## Configuration

Configuration lives in `~/.claude/explain-selection/config.env` with `EXPLAIN_SELECTION_` prefixed variables:

- `EXPLAIN_SELECTION_MAX_CHARS` (default 200000) — Maximum selection length in characters
- `EXPLAIN_SELECTION_LONG_SELECTION` (default truncate) — How to handle long selections: `truncate` or `tempfile` (for mode A new-window fallback)
- `EXPLAIN_SELECTION_PROMPT_TEMPLATE` — Path to the prompt template file. The code default is `<plugin root>/templates/explain-prompt.txt`; install writes config.env so it points at `~/.claude/explain-selection/explain-prompt.txt`, the editable copy.
- `EXPLAIN_SELECTION_REMEMBER_TARGET_MINUTES` (default 10) — How long to remember the user's manual session pick from the chooser
- `EXPLAIN_SELECTION_FALLBACK_CWD` (default `$HOME`) — The directory to use as cwd when no better choice is available

Environment only (cannot be set in config.env):

- `EXPLAIN_SELECTION_PLUGIN_ROOT` (default `$CLAUDE_PLUGIN_ROOT`) — Path to the plugin installation directory
- `EXPLAIN_SELECTION_HOME` (default `~/.claude/explain-selection`) — Base directory for registry, logs and configuration; the home decides where config.env is read from

The prompt template at `~/.claude/explain-selection/explain-prompt.txt` contains the text sent to Claude Code. The `{text}` placeholder is replaced by the selection.

## CLI

Once the plugin is enabled, these commands are available inside Claude Code's Bash tool or as `<plugin root>/bin/explain-selection`:

- `explain-selection version` — Print the package version
- `explain-selection sessions` — List live sessions with columns: pid, status, kind, registered or unregistered, label, cwd
- `explain-selection send --pid <pid> --text -|<string>` — Send a message to a specific session. Text from stdin with `-` or as a string argument.
- `explain-selection install [--shortcut KEY] [--dry-run] [--plugin-root PATH]` — Install the runtime, workflow bundle and keyboard shortcut. Shortcut format: `@` for Command, `~` for Option, `^` for Control, `$` for Shift, then the letter (e.g., `@~e` for Command-Option-E).
- `explain-selection doctor` — Check the installation. Output format: one line per check `[ok|warn|fail|skip] name: detail`, each warn or fail followed by an indented `fix: ...` line, last line `doctor: N ok, N warn, N fail, N skipped`. Exit code 1 when any check failed.

Doctor checks: home, venv, version, shim, config, template, plugin-enabled, settings-files, agents, one per live session (registered or not, socket present, tmux, uptime), stale-entries, inbound-policy (`crossSessionInbound` accept, hold or refuse from Claude Code settings), and macOS only: services-bundle, shortcut, osascript.

## How it works

### Hooks and registry

SessionStart and CwdChanged hooks register each session in `~/.claude/explain-selection/sessions/<pid>.json` with mode 0600. Each entry contains the pid, cwd, tty, tmux pane, inbox socket path and token. SessionEnd removes the entry. Tokens never appear in logs.

The registry directory `~/.claude/explain-selection/sessions/` has mode 0700. Stale entries are pruned only when the pid is absent from `claude agents --json` and the process is dead.

### Target ladder

When several sessions are running, the hooks record each session's tmux pane in the registry; at hotkey time the plugin asks tmux for the active pane of the attached client and matches it against those entries. The terminal tty is read through AppleScript (iTerm2 `tty of current session of current window`, Terminal.app `tty of selected tab of front window`) and matched against the registry.

If the focused session cannot be determined, the plugin checks if the user picked a session from the chooser within the configured `remember_target_minutes` and that session is still running. Otherwise it filters by idle sessions. If exactly one idle session exists, it uses that. If still ambiguous, an AppleScript chooser dialog lists sessions (idle first, then busy, then waiting) and remembers the pick.

### Socket delivery

The plugin connects to the session's inbox socket with a short timeout and writes newline-delimited JSON: when the session is registered, first an auth line carrying the inbox token from the registry, then the user message line; unregistered sessions get only the message line, derived from the pid-based socket path. The server sends no reply and does not close the connection; the plugin closes after writing.

### Deep link fallback

When no interactive session is running, the plugin opens a new Claude Code window with the `claude-cli://` deep link scheme: `claude-cli://open?cwd=<cwd>&q=/explain-selection:explain <text>`. The `q` parameter holds at most 5000 characters; longer selections are shortened and a notification says so.

### Security

Inbox tokens are secrets stored in mode 0600 registry files under a mode 0700 directory. They never appear in logs, test fixtures or committed files. Sessions that bypass permission prompts hold token-less messages for approval, so run the plugin's hooks (restart sessions after enabling the plugin) to enable token-bearing delivery.

## Troubleshooting

### Run doctor

`/explain-selection:doctor` prints one line per check with a fix for every warn or fail. If the command is not found, the plugin is not enabled or the runtime is not installed. Run `/explain-selection:install`.

### Shortcut not in the menu

Relaunch your terminal apps (iTerm2, Terminal, Ghostty) or open System Settings > Keyboard > Keyboard Shortcuts > Services > Text and verify the Explain selection entry exists and has a checkmark.

### Automation permission

macOS prompts once per app for Automation permission. The prompt appears the first time the hotkey runs with several sessions open. To check the permission: System Settings > Privacy & Security > Automation, then look for the entry that allows the Quick Action runner (Automator or WorkflowServiceRunner) to control iTerm2 or Terminal.

### Messages held

If messages appear in the held queue instead of arriving immediately, check the `crossSessionInbound` policy in Claude Code's settings files. The policy has three values: `accept` (deliver immediately), `hold` (queue for review), or `refuse` (reject). The doctor check `inbound-policy` reports the current setting.

## Limitations

- macOS only for the hotkey. The CLI and skills work anywhere Claude Code runs.
- Ghostty must pass the selection to the Services menu; if it does not, use the Shortcuts route in the Alternatives section.
- Selecting text inside Claude Code's own output captures the hard-wrapped rendering, not the original Markdown. Use `/btw`'s `c` key (copy answer as raw Markdown) instead.
- No clipboard fallback for terminals that do not pass the selection to Services.
- A custom `EXPLAIN_SELECTION_HOME` breaks the hotkey because the workflow bundle hardcodes the default shim path at `$HOME/.claude/explain-selection/capture`.
- Sessions that bypass permission prompts hold token-less messages. Run the plugin's hooks (restart sessions after enabling the plugin) to get token-bearing delivery.

## Alternatives not built

### Mode C: terminal automation with `/btw`

The plugin implements mode B (inbox socket injection). Mode C from the plan types `/btw explain: ...` directly into the TUI through terminal automation. This gives zero context pollution (the message is not in the transcript) at the cost of being visible in the UI. Not built in 0.1.0 but described here for users who want that property.

iTerm2 has an AppleScript `write` command that targets a session by tty and accepts a `newline no` parameter to compose without submitting:

```applescript
tell application "iTerm2"
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if tty of s is "$devtty" then write s text "/btw explain: $text" newline no
      end repeat
    end repeat
  end repeat
end tell
```

Under tmux, the best mode C available anywhere:

```bash
tmux send-keys -t "$pane" -l '/btw explain: the selected text'
```

No AppleScript, no Accessibility, no TCC prompt. Targets a specific pane whether or not it is active or attached.

Terminal.app has `do script "…" in <tab>` where tabs expose `tty`, `selected` and `busy`, but whether `do script` reaches the pty of a running foreground TUI rather than a shell is unverified.

Ghostty 1.3.0+ has `input text` AppleScript. Ghostty 1.2.3 has a Shortcuts intent Input Text to Terminal that does the same job.

### Ghostty Shortcuts route

Ghostty 1.2+ supports Shortcuts (App Intents). Create a shortcut: Get Details of Terminal > Selected Text > Run Shell Script > `capture.sh`. Assign a keyboard shortcut in the shortcut's details. Requires `macos-shortcuts = ask` or `allow` in Ghostty config. This needs no Accessibility and no Services.

The `shortcuts` CLI has no setter for key assignments, so the shortcut can be shipped signed but the key assignment is UI-only.

### iTerm2 Python API

iTerm2 Settings > General > Magic > Enable Python API. Download the Python runtime, drop an AutoLaunch script registering an `@iterm2.RPC`, bind it with Invoke Script Function. Read the selection with `async_get_selection_text()` and send with `async_send_text()` for mode C delivery.

## Development

- `make check` — lint, strict typecheck, unit tests (fail-fast, under 30 seconds)
- `make test-all` — everything including slow and integration tests
- `make layers` — verify module layering with `import-linter`
- `make validate` — `claude plugin validate .` (not strict, because the root `CLAUDE.md` triggers an accepted warning)

See `AGENTS.md` for the full development rules: pyright strict, no escape hatches, pure core, explicit dependencies, fast deterministic tests.
