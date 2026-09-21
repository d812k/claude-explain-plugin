# Review follow-ups

Items from reviews that were deliberately deferred. Each item names the phase in which it should be addressed.

## Phase 5-6: install, doctor (resolved)

- Resolved: The wrappers in `bin/` exit 0 silently when no interpreter is found. The `venv` check in `doctor` now detects and reports a missing venv.
- Resolved: `LiveSession.started_at_ms` and `RegistryEntry.tmux` are now used in `doctor` session output lines.
- Open: The `stdin` parameter of `CommandRunner.run` is stored but never read. Either use it or remove it.

## Deferred to post-0.1.0

Items deferred from 0.1.0 to keep the scope manageable:

- Command-C clipboard fallback for terminals that do not pass the selection to Services. It would need sleep polling of the pasteboard, increasing latency.
- Templating the workflow bundle for a custom `EXPLAIN_SELECTION_HOME`. The bundle hardcodes `$HOME/.claude/explain-selection/capture`, so a non-default home breaks the hotkey unless the bundle is regenerated at install time.
- On Linux, `--dry-run` reports the two macOS-only steps as `skipped` rather than `planned`.
- Eval sandbox: `claude plugin eval .` runs two cases; in the `list-sessions` case the sandbox denied the Bash call, so the LLM judge fails although the Bash grader passes. The suite is informational for now.
