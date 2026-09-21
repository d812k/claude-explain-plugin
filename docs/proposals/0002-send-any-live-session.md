# Proposal 0002: send and sessions accept any live session

Status: accepted on 2026-09-21. Extends proposal 0001; route B (inbox-socket injection)
is unchanged.

## 1. Context

- `claude agents --json` reports two kinds of live session, `interactive` and `background`.
- Until now every use case dropped `background` sessions twice: the `AgentsCli` adapter
  skipped them and `join_targets` filtered them again. `explain-selection send --pid`
  answered `no live interactive session with pid` and `explain-selection sessions` never
  listed them.
- The hotkey path (`deliver_selection`) must stay interactive-only: a person is looking at
  those terminals, and an unattended job must not receive a selection meant for them.
- On a Linux development box the only session available to post into is a background one,
  so the explicit `send` command was unusable there.

## 2. Decision

- `deliver_selection` keeps targeting `kind == interactive` sessions only.
- `send_message(pid, ...)` and `list_sessions` accept every live session that
  `claude agents --json` lists, including `background` ones. The user names the target
  explicitly, and a background session (for example a Claude Code background job) is a
  legitimate recipient.

## 3. API change

- `join_targets(sessions, entries, *, include_background: bool = False)`: the default keeps
  the current behaviour; `send_message` and `list_sessions` pass `include_background=True`.
- `SessionLister.list_interactive()` becomes `SessionLister.list_live()` and returns
  sessions of every known kind. `AgentsCli` maps the reported `kind` to `SessionKind`
  instead of dropping background rows; rows with an unknown kind are still skipped. Kind
  filtering lives in the domain only.
- `SessionSummary` gains a `kind: SessionKind` field.
- The `sessions` command prints a kind column (`interactive` or `background`) after the
  status column: `pid  status  kind  registered|unregistered  label  cwd`.
- The error text `no live interactive session with pid` becomes `no live session with pid`.

## 4. Consequences

- The `send` skill can address background jobs; its description of the `sessions` output
  gains the kind column.
- Hooks, the registry file format, the plugin manifest and the hotkey behaviour are
  unchanged.
