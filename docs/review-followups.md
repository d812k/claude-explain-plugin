# Review follow-ups from phase 1-2

Items from the phase 1-2 review that were deliberately deferred. Each item names the phase in which it should be addressed.

## Phase 3-4: deliver end to end, skills

- Truncation at `max_chars` is invisible to the user. `Selection.original_chars` and `Selection.truncated` in `src/explain_selection/domain/selection.py` are never read. Notify the user when a selection was truncated.
- Liveness pruning of registry entries in `src/explain_selection/services/deliver.py` uses absence from `claude agents --json` rather than a pid liveness check as in plan section 4.3. Decide whether to check the pid before deleting an entry.

## Phase 5-6: install, doctor

- The wrappers in `bin/` exit 0 silently when no interpreter is found. `doctor` must detect a missing venv and report it.
- Fields that are stored but never read: `LiveSession.started_at_ms`, `RegistryEntry.tmux`, the `SessionKind.BACKGROUND` filter in `join_targets`, and the `stdin` parameter of `CommandRunner.run`. Either use them in `doctor` output or remove them.
