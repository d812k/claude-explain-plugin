# AGENTS.md — explain-selection

Rules for coding agents (and humans) in this repo. Design principle: every change is
checked by machines before a human sees it. The type checker is the first reviewer, the
test suite the second, a human the last. Prefer boring, explicit, checkable code.

The product is a Claude Code plugin: select text in a macOS terminal, press a hotkey, and
the text is delivered into the running Claude Code session through its inbox socket.
The design is in `explain-selection-plugin-plan.md`; route B (inbox-socket injection) is
decided. Do not reopen that decision.

## 0. The loop

1. Read the module you will touch and its tests before editing.
2. Make one small change: one behaviour, ideally one module.
3. Run `make check`. Do not continue while it is red.
4. Repeat until the task is done. Finish with `make check` green.
5. Report: what changed, why, the final `make check` result line, and open risks.

Never batch unrelated changes before running the check. Never declare a task finished
while any check fails. If you could not run a check, say so plainly. Do not claim
verification you did not perform.

## 1. Commands — the single source of truth

- `make check` — lint, strict typecheck, unit tests; fail-fast. Budget: under 30 seconds.
- `make fmt` — `ruff format` and `ruff check --fix`.
- `make lint` — `ruff format --check` and `ruff check`.
- `make type` — `pyright` in strict mode.
- `make test` — `pytest`, unit tests only; `slow` and `integration` are excluded. Budget: under 10 seconds.
- `make prop` — property tests with the larger Hypothesis profile.
- `make test-all` — everything, including `slow` and `integration`. Run before a PR.
- `make layers` — `lint-imports`; enforces the module layering in section 4.
- `make validate` — `claude plugin validate .` (not `--strict`, because the root `CLAUDE.md` triggers a warning we accept); needs the `claude` binary, so it runs in `make test-all`, not in `make check`.

Everything runs through `uv run`. Never install packages globally. If a command in this
list is missing or wrong, fix the `Makefile` in the same change.

## 2. Definition of done

- `make check` is green and, for anything touching I/O, `make test-all` too.
- Every behaviour change has a test in the same commit. Bug fixes start with the failing test.
- New public functions are fully annotated and have a one-line docstring.
- No new `Any`, `cast`, or ignore comments without a reason (section 3).
- No new dependency unless it was agreed first (section 7).
- The change summary follows step 5 of the loop.

## 3. Types — pyright strict, no escape hatches

- Every function signature is fully annotated, including return type. This includes tests.
- `Any` is forbidden unless commented on the same line: `# Any: <reason>`.
- Bare `# type: ignore` is disabled. Use `# pyright: ignore[<rule>]  # <reason>` and only
  for third-party typing gaps. Unnecessary ignores are errors.
- Model data with types, not dicts: `@dataclass(frozen=True, slots=True)` internally,
  `pydantic.BaseModel` only at I/O boundaries (section 5). Use `Literal`, `Enum`, `NewType`
  for identifiers and states; `Protocol` for interfaces; `Final` for constants.
- Sum types are unions of frozen dataclasses handled with `match` and `assert_never` in the
  default arm, so adding a variant makes the type checker list every unhandled site.
- Parse, don't validate: convert optional or raw input into required, typed fields once, at
  the boundary. Do not thread `Optional` through the core.
- Never lower strictness in `pyproject.toml` to get green.

## 4. Structure — small modules, explicit dependencies, pure core

- Modules stay under about 300 lines and do one thing. Each package's `__init__.py` defines
  `__all__`; that is the public interface. Anything else is private. Do not import private
  names from outside the package, including in tests.
- Layering, enforced by `make layers`: `domain` (pure, no I/O) is imported by `services`,
  which is imported by `adapters` (I/O: Unix sockets, subprocesses, files, tmux), which is
  imported by `entrypoints` (hook and CLI commands). Lower layers never import higher ones.
- Pure core, imperative shell: target selection, message templating, registry parsing and
  socket-path resolution are pure functions over data. Side effects live in adapters.
- No module-level mutable state, singletons, or import-time side effects (no config reads,
  no connections, no I/O at import). Dependencies are passed explicitly: a frozen `Deps`
  dataclass built once in each entrypoint's `main()` and handed down.
- Time, randomness, IDs, environment, and process information are injected, never read
  from globals inside the core.
- Subprocesses (`claude agents --json`, `tmux`, `osascript`, `ps`) run only in adapters via
  `subprocess.run` with an explicit `timeout`, an argument list, and never `shell=True`.
- Errors: typed exceptions in `src/explain_selection/errors.py`. No bare `except:`.
  `except Exception` only at an entrypoint, where it is logged and mapped to an exit code.
- No `async`. Everything this plugin does is a short synchronous command.
- Logging via `logging.getLogger(__name__)`. `print` is allowed only in `entrypoints/cli.py`.
- Hook entrypoints must finish well under the 5 second hook timeout: import lazily, do no
  network, and never print to stdout (a `SessionStart` hook's stdout is injected into the
  Claude Code session).

## 5. Boundaries

- All external input (hook JSON on stdin, registry files, `claude agents --json` output,
  environment, CLI arguments, `config.env`) is validated with pydantic at the boundary and
  converted to internal types before it goes inward. Raw dicts never cross a layer.
- Configuration is one `pydantic-settings` `Settings` object, constructed in `main()` and
  passed down. Nothing reads `os.environ` elsewhere.
- The registry directory and its files hold per-session inbox tokens. They are created with
  mode `0700` and `0600`; tokens never appear in logs, test fixtures, or committed files.

## 6. Tests — fast, deterministic, explicit

- Unit tests (default, run by `make check`): no network, no filesystem outside `tmp_path`,
  no `sleep`, no real clock, no subprocesses, no real sockets, no running `claude`. Each
  finishes well under a second; a 5 second hard timeout fails the test.
- Adapters are behind `Protocol`s; unit tests use in-memory fakes, not mocks of internals.
- Anything else is marked `@pytest.mark.slow` or `@pytest.mark.integration` and runs only
  in `make test-all`. Integration tests that need a live Claude Code session must skip
  cleanly when none is available.
- Minimal pytest magic: no `autouse` fixtures; one `tests/conftest.py`, nothing deeper;
  fixtures are plain functions returning values. Prefer calling constructors directly.
  `monkeypatch` only at process boundaries (env, time), never on internal code.
- Property tests with Hypothesis for pure functions: registry parsing, socket-path
  resolution, message templating, target ranking. Mark them `@pytest.mark.prop`. The default
  profile is small so `make check` stays fast; `make prop` runs the large profile.
- Test the public API (`__all__`), not private helpers. If a helper needs its own test, it
  is probably a module.
- Warnings are errors. `xfail` is strict. Tests never contain `assert True` or conditional asserts.

## 7. Dependencies and tooling — one way to do each thing

- `uv` with a committed `uv.lock`. Add with `uv add` or `uv add --dev`; never edit the
  lockfile by hand. The Python version is pinned in `.python-version`.
- Propose before adding a runtime dependency; prefer the standard library. Explain what it
  replaces and why the stdlib does not suffice.
- The stack is fixed: `pydantic` and `pydantic-settings` (validation and config), `ruff`
  (lint and format), `pyright` (types), `pytest` and `hypothesis` (tests), `import-linter`
  (layers). The Unix socket client uses the stdlib `socket` module. Do not introduce
  parallel tools for the same job.

## 8. Never

- Start dev servers, watchers, REPLs, or any long-lived process and leave it running. If a
  manual check truly needs one, run it under `timeout 30 ...` and confirm it exited.
- Silence a check to get green: `# noqa`, ignore comments, deleting or skipping tests,
  relaxing config. Fix the cause or stop and report.
- Touch files outside the task's scope, or refactor "while you are there".
- Post into a real Claude Code session from tests, or read a real registry token in tests.
- Commit generated files, secrets, `.env`, registry files, or caches.
- Use `time.sleep` for synchronisation anywhere.

## 9. When stuck

- After three failed attempts to make a check green, stop. Report the exact error, what
  you tried, and your best hypothesis. Do not keep looping.
- Anything that changes a public API, the registry file format, the plugin manifest, a
  dependency, or the layering needs a short written proposal before code.

## 10. Repo map

    .claude-plugin/plugin.json      plugin manifest; version equals pyproject.toml
    hooks/hooks.json                SessionStart, CwdChanged, SessionEnd → bin/ wrappers
    skills/                         explain, install, doctor, send (SKILL.md each)
    bin/                            POSIX sh wrappers: explain-selection-{register,unregister,capture}
    templates/explain-prompt.txt    the mode B prompt; {text} is replaced by the selection
    docs/proposals/                 accepted decisions; 0001 covers runtime, wrappers, registry
    src/explain_selection/
      domain/                       pure logic, frozen dataclasses, no I/O
      services/                     use-cases composing domain + adapter protocols
      adapters/                     socket client, subprocess runners, registry files, tmux
      entrypoints/                  register, unregister, capture, cli; settings.py, deps.py
      errors.py                     typed exceptions
    tests/
      unit/  prop/  integration/  conftest.py  fakes.py  builders.py
    Makefile  pyproject.toml  uv.lock  .python-version  AGENTS.md  CLAUDE.md
    explain-selection-plugin-plan.md   the design; route B is decided

## Why these rules

Machine-checkable feedback in the loop produces the largest measured gains in agent coding
(type-constrained decoding, compiler-feedback repair, verification loops). Fast explicit
tests and explicit context passing are the substance of the strongest practitioner case
for agent-friendly languages; strict typing gives Python that property while keeping its
strongest-in-class repository-level track record. Agents fail disproportionately when they
must manage long-lived processes and when context is consumed by large, tangled modules,
hence sections 4 and 8. Sources: `~/llm-language-for-agentic-systems.md`.
