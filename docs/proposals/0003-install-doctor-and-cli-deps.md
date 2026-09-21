# Proposal 0003: install, doctor and CLI deps

Status: accepted on 2026-09-21. Phases 5 and 6 add the install and doctor subcommands, change the CLI `run()` signature, and integrate macOS Services registration.

## 1. Context

- Phase 1-2 built the hooks, registry, and target selection. The install process was manual: the user ran `uv sync` and enabled hooks in their config. Phase 5 automates installation through a bootstrap script and a Python installer, then phase 6 adds `doctor` to verify the setup.
- On macOS the hotkey is delivered through a Services workflow bundle that execs a shim. The Services menu and keyboard shortcut are set through the `pbs` services database with `defaults write` and verified with `defaults read`.
- The CLI `run()` signature took five parameters, mixing concerns: `argv`, `stdin_text`, `deps_factory`, `out`, `err`. The `install` and `doctor` subcommands need their own dependencies (filesystem writes, subprocess calls, macOS Services registration) that differ from the core commands.

## 2. Decisions

### 2.1 Install: venv setup and macOS Services registration

- Bootstrap script `scripts/bootstrap.sh` checks for `uv`, creates the venv at `~/.claude/explain-selection/venv` with Python 3.12, installs the plugin package, then execs `explain-selection install`.
- The Python installer runs six steps: `home` (directory layout), `config` (write `config.env` once), `prompt` (copy the template once), `shim` (write the `capture` executable every time), `service` (copy the workflow bundle to `~/Library/Services`), `shortcut` (assign the hotkey through `pbs` with `defaults write`, verify with `defaults read`).
- Each step prints one line: `[done|skipped|planned|failed] name: detail`. Exit code 1 if any step fails. A `Next steps:` block follows the step lines.
- The `shortcut` step verifies the assignment; if verification fails the step is `failed` and the user sets it manually in System Settings > Keyboard > Keyboard Shortcuts > Services > Text > Explain selection.
- Command-line options: `--shortcut KEY` (format: `@` Command, `~` Option, `^` Control, `$` Shift, then the letter), `--dry-run`.

### 2.2 Doctor: read-only diagnostics

- `explain-selection doctor` prints one line per check with an exact fix for every warn or fail. Pure: no writes, no changes, no side effects.
- Checks: home, venv, version, shim, config, template, plugin-enabled, settings-files, agents, one per live session, stale-entries, inbound-policy, and macOS only: services-bundle, shortcut, osascript.
- Uses `LiveSession.started_at_ms` and `RegistryEntry.tmux` in session output lines to show more context.
- The skill `/explain-selection:doctor` will wrap it.

### 2.3 CLI deps: CliDeps dataclass

- The `run()` signature changes from `run(argv, stdin_text, deps_factory, out, err)` to `run(argv, CliDeps, out, err)`, where `CliDeps` is a frozen dataclass holding `stdin_text`, `deps_factory` for core commands, and also `install_deps` and `doctor_deps` for the new subcommands.
- Each `main()` builds one `CliDeps` object and passes it down. The `version` subcommand still touches no filesystem before parsing.

## 3. Explicitly deferred

Items deferred from 0.1.0 to keep the scope manageable:

- Command-C clipboard fallback for terminals that do not pass the selection to Services. It would need sleep polling of the pasteboard, increasing latency.
- Templating the workflow bundle for a custom `EXPLAIN_SELECTION_HOME`. The bundle hardcodes `$HOME/.claude/explain-selection/capture`, so a non-default home breaks the hotkey unless the bundle is regenerated at install time.
- On Linux, `--dry-run` reports the two macOS-only steps as `skipped` rather than `planned`.
- Eval sandbox: `claude plugin eval .` runs two cases; in the `list-sessions` case the sandbox denied the Bash call, so the LLM judge fails although the Bash grader passes. The suite is informational for now.

## 4. Consequences

- The install skill automates the entire setup: one command from a fresh checkout to a working hotkey. The user must still relaunch terminal apps for the Services menu to refresh and approve the automation prompt on first use.
- The doctor command gives actionable diagnostics. It replaces the silent failure mode where the wrapper exits 0 and the user sees nothing.
- The `CliDeps` change isolates the dependencies each subcommand needs, preventing `version` from accidentally touching the filesystem and keeping the core commands (register, unregister, capture, send, sessions) separate from the new install and doctor concerns.
- Review follow-ups from phase 1-2 are resolved: the `venv` check in `doctor` detects a missing venv; `LiveSession.started_at_ms` and `RegistryEntry.tmux` are used in `doctor` session lines. The unused `CommandRunner.run(stdin=)` parameter remains open.
