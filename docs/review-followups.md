# Review follow-ups from phase 1-2

Items from the phase 1-2 review that were deliberately deferred. Each item names the phase in which it should be addressed.

## Phase 5-6: install, doctor

- The wrappers in `bin/` exit 0 silently when no interpreter is found. `doctor` must detect a missing venv and report it.
- Fields that are stored but never read: `LiveSession.started_at_ms`, `RegistryEntry.tmux`, and the `stdin` parameter of `CommandRunner.run`. Either use them in `doctor` output or remove them.
