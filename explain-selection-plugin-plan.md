# Plan: `explain-selection` — a Claude Code plugin for "select text → hotkey → explain"

Target: macOS 26.2, Claude Code 2.1.276, iTerm2 3.6.11 / Ghostty 1.2.3 / Terminal.app.

---

## 1. Verdict

**The decision: mode B (inject into the running session) is the chosen route.**

| # | Mode | What happens | Deps / permissions | Status |
|---|------|--------------|--------------------| ------ |
| **B** | **Inject into the running session** | Post one JSON line to that session's inbox socket; the text arrives as a turn in the session you were already in, **even while Claude is mid-turn** | none beyond the plugin (no Accessibility) | **Chosen** |
| **A** | **New CC window** | `open "claude-cli://open?cwd=…&q=explain:%20…"` opens a *new* terminal window running Claude Code with the prompt pre-filled (you press Enter) | none — handler already installed on this Mac | **Fallback** (when no live session) |
| **C** | **Literally type `/btw explain: …`** | Terminal automation types the command into the focused CC session; answer stays out of the conversation context | Automation (iTerm2) or Accessibility (System Events) TCC grant | **Documented alternative, not built** |

**Why B?** It delivers the selection into the session you're already working in, with no size cap beyond ~1M chars, and **removes the entire Automation/Accessibility (TCC) dependency from delivery** — the only remaining permission surface is the capture side.

**Why A stays as a fallback:** Mode B requires a live session. When `claude agents --json` returns no interactive session, the hotkey must still do something — A is the natural degenerate case. Same capture layer, same hotkey, zero-latency path selection in `find-target.sh`.

**What a plugin cannot do** (so the plan does not pretend otherwise):

- Plugins cannot ship keybindings, and no Claude Code keybinding action can run a slash command or insert text. (`~/.claude/keybindings.json` actions are UI-only: `chat:submit`, `app:interrupt`, …)
- Claude Code's TUI cannot see the terminal emulator's mouse selection. Nothing inside CC can.

⇒ The global hotkey and the selection capture must live in **macOS** (a Quick Action / Shortcut / Hammerspoon binding). The plugin's job is to **ship those artifacts, install them, and own the receiving end**. That is a legitimate plugin: it is how a plugin ships an OS integration.

---

## 2. Verified facts this plan rests on

| Fact | How verified |
|---|---|
| `claude-cli://open?q=…&cwd=…&repo=…` opens a new terminal window with the prompt **populated but not sent**; `q` max **5,000 chars**, `%0A` for newlines; `cwd` rejects UNC/`..`; warning line `Prompt from an external link` is shown | [deep-links docs](https://code.claude.com/docs/en/deep-links) |
| Handler is `~/Applications/Claude Code URL Handler.app`, scheme `claude-cli`, registered on first prompt of an interactive session | docs + `plutil -p` on the bundle on this Mac ✅ |
| Deep link reuses **the terminal of your most recent interactive session** (iTerm2, Ghostty, kitty, Alacritty, WezTerm, Terminal.app) | docs |
| Every session binds an inbox socket; path + per-session token are exported to hooks **and Bash commands** as `CLAUDE_CODE_MESSAGING_SOCKET` / `CLAUDE_CODE_MESSAGING_TOKEN`; docs explicitly bless "a script or hook to post into a session" | [cross-session-messaging docs](https://code.claude.com/docs/en/cross-session-messaging#the-sessions-inbox-socket) |
| Exact wire format:<br>`{"type":"auth","token":"$CLAUDE_CODE_MESSAGING_TOKEN"}`<br>`{"type":"user","message":{"role":"user","content":"hello"}}`<br>piped to `nc -U "$CLAUDE_CODE_MESSAGING_SOCKET"` | the CLI's own debug string, **and a live end-to-end test into this session** ✅ |
| Socket path is `${XDG_RUNTIME_DIR:-/tmp}/cc-socks/<pid>.sock`, falling back to `/tmp/cc-socks-<uid>/<pid>.sock` when the path exceeds 103 bytes; dir `0700`, socket `0600` | binary + `ls -l` ✅ (`/tmp/cc-socks/5982.sock`) |
| Delivery timing: read **between tool calls** during an active turn (never interrupts a running tool); starts a new turn if idle | docs + live test ✅ |
| Injection works from a **truly external** process — a `launchd` job with `ppid=1` and **no controlling tty** — when it presents the token in the auth line. Delivery involves no tty and no process-tree relationship | live test ✅ (`nc_exit=0 ppid=1 tty=??`, message delivered) |
| `/bin/bash` is **3.2.57**; `/bin/zsh` is 5.9. The plan's pid-walk runs clean under bash 3.2 | run locally ✅ |
| A posted message is framed as *from another session*: slash commands in it **do not execute**, it can't approve permissions, and it **does** enter the conversation | docs + live test ✅ |
| `claude agents --json` prints `{pid, cwd, kind, startedAt, sessionId, name, status}` for interactive + background sessions, no TTY needed, ~0.1 s | run locally ✅ |
| `ps -o tty= -p <pid>` maps a session pid → `ttys005`; a hook/Bash child shows `??` for itself but `$PPID` is the CC process with the right tty | run locally ✅ |
| `/btw <question>` is out-of-history, **available while Claude is working**, has **no tool access**, single response, replays the newest 20 side exchanges | [interactive-mode docs](https://code.claude.com/docs/en/interactive-mode#side-questions-with-btw) |
| Plugin manifest supports `skills` (adds to default `skills/`), `commands`, `agents`, `hooks`, `mcpServers`, `lspServers`, `outputStyles`, `bin/` on the Bash PATH, `userConfig`; **no `keybindings`** | [plugins-reference](https://code.claude.com/docs/en/plugins-reference) |
| `${CLAUDE_PLUGIN_ROOT}` expands in hook commands and skill bodies; must be quoted in shell-form hooks; **not** exported to Bash-tool commands | same |
| Dev loop: `claude plugin init <name> --with skills,hooks` scaffolds at `~/.claude/skills/<name>/` (auto-loads as `<name>@skills-dir`); `claude --plugin-dir <path>`; `claude plugin validate <path> --strict`; `claude plugin eval <path>` | `--help` locally ✅ |
| iTerm2, Terminal.app **and** Ghostty all implement `NSServicesMenuRequestor` (selection → Services) and override `accessibilitySelectedText` | binary symbols + Ghostty v1.2.3 source ✅ |
| iTerm2 exposes a `selection` session variable, an AppleScript `write … newline no`, and session `tty`; it has **no** key-binding action that runs a shell command | iTerm2 docs + `iTerm2.sdef` ✅ |
| Ghostty ≥1.2 ships Shortcuts intents: *Get Details of Terminal → Selected Text*, *Input Text to Terminal*, *New Terminal* (`command`, `workingDirectory`), gated by `macos-shortcuts` | Ghostty source/PR #7634 ✅ |
| `/usr/bin/jq` and `/usr/bin/nc` exist; **`socat` does not** → use `nc -U`. `python3` is Homebrew-only here → don't depend on it | run locally ✅ |

Channels (`--channels`) were evaluated and **rejected**: research preview, requires an MCP server plugin on an Anthropic allowlist, Bun, and a session started with a flag. The inbox socket does the same job with zero setup.

---

## 3. Architecture

```
  ┌─ macOS (outside Claude Code) ────────────┐        ┌─ Claude Code ─────────────────┐
  │ selection + ⌘⌥E                          │        │                               │
  │   └─ capture.sh  (text on stdin/clipbd)  │        │  SessionStart hook            │
  │        ├─ sanitize / cap length          │        │    └─ register-session.sh ────┼──┐
  │        ├─ pick target: find-target.sh ───┼────────┼──> claude agents --json       │  │
  │        └─ deliver:                       │        │                               │  │
  │            A  open claude-cli://open?q=… ┼────────┼──> NEW window, prompt filled  │  │
  │            B  nc -U …/cc-socks/<pid>.sock┼────────┼──> running session, new turn  │  │
  │            C  osascript → write text     ┼────────┼──> types "/btw explain: …"    │  │
  └──────────────────────────────────────────┘        └───────────────────────────────┘  │
                     ▲                                                                   │
                     └──────────  ~/.claude/explain-selection/sessions/<pid>.json  ◄──────┘
                                  {sessionId, pid, tty, cwd, name, socket, token}  (0600)
```

Of the three delivery arrows, **B is the one the plugin builds**; A runs only when no live session exists; C is documented, not built (§4.6).

Two independent halves; each is useful without the other. The registry file exists **only** to carry the per-session `CLAUDE_CODE_MESSAGING_TOKEN` out to the hotkey script — without it, mode B still works but the post counts as an unverified peer (delivered in normal sessions, held for approval in `bypassPermissions` sessions).

---

## 4. Plugin contents

```
explain-selection/
├── .claude-plugin/plugin.json
├── hooks/hooks.json                  SessionStart / SessionEnd / CwdChanged
├── scripts/
│   ├── register-session.sh           writes the registry entry (+token)
│   ├── unregister-session.sh
│   ├── capture.sh                    hotkey entry point: stdin | clipboard → route
│   ├── find-target.sh                frontmost tty → pid → socket, else picker
│   ├── deliver-newwindow.sh          mode A (fallback)
│   ├── deliver-inject.sh             mode B (primary)
│   └── lib.sh                        sanitize, urlencode, json, notify, log
├── templates/
│   └── explain-prompt.txt            the actual prompt used by mode B
├── assets/
│   ├── ExplainSelection.workflow/    Automator Quick Action template
│   ├── explain-selection.lua         Hammerspoon snippet (optional path)
│   └── iterm2-keybinding.md          native iTerm2 recipe
├── skills/
│   ├── explain/SKILL.md              receiving end for mode A + manual use
│   ├── install/SKILL.md              installs the hotkey, walks TCC prompts
│   ├── doctor/SKILL.md               diagnoses handler/permissions/registry/B failure modes
│   └── send/SKILL.md                 "send this to my other session" (reuses B)
├── evals/                            claude plugin eval cases
└── README.md
```

### 4.1 `plugin.json`

```json
{
  "name": "explain-selection",
  "description": "Select text anywhere on macOS, press a hotkey, get Claude Code to explain it.",
  "version": "0.1.0",
  "hooks": "./hooks/hooks.json",
  "userConfig": {
    "mode": { "type": "string", "title": "Default delivery", "description": "newwindow | inject | btw" },
    "prompt_template": { "type": "string", "title": "Prompt", "description": "Default: 'explain: {text}'" },
    "max_chars": { "type": "string", "title": "Max selection characters" },
    "auto_submit": { "type": "string", "title": "Press Enter for me (inject/btw modes)" }
  }
}
```

`skills/` is picked up by default. `userConfig` values reach hook commands as `${user_config.mode}` / `CLAUDE_PLUGIN_OPTION_MODE`; the capture script (which runs **outside** CC) reads the same settings from `~/.claude/explain-selection/config.env`, written by `/explain-selection:install`.

### 4.2 `hooks/hooks.json`

```json
{
  "hooks": {
    "SessionStart":  [ { "hooks": [ { "type": "command", "command": ["${CLAUDE_PLUGIN_ROOT}/scripts/register-session.sh"], "timeout": 5 } ] } ],
    "CwdChanged":    [ { "hooks": [ { "type": "command", "command": ["${CLAUDE_PLUGIN_ROOT}/scripts/register-session.sh"], "timeout": 5 } ] } ],
    "SessionEnd":    [ { "hooks": [ { "type": "command", "command": ["${CLAUDE_PLUGIN_ROOT}/scripts/unregister-session.sh"], "timeout": 5 } ] } ]
  }
}
```

Exec form (array) so `${CLAUDE_PLUGIN_ROOT}` expands without quoting traps. Hooks print nothing and exit 0 — a `SessionStart` hook that writes to stdout injects context into every session, which we do not want.

### 4.3 `register-session.sh` (the one non-obvious script)

```bash
#!/bin/bash
set -euo pipefail
in=$(cat)                                     # hook JSON on stdin
sid=$(printf '%s' "$in" | jq -r '.session_id // empty')
cwd=$(printf '%s' "$in" | jq -r '.cwd // empty')

# Walk up to the claude process: our own tty is "??", the parent's is the real one.
pid=$PPID; tty="??"
for _ in 1 2 3 4 5; do
  read -r ppid tty <<<"$(ps -o ppid=,tty= -p "$pid" 2>/dev/null || true)"
  [[ "${tty:-??}" != "??" ]] && break
  pid=${ppid:-1}; [[ $pid -le 1 ]] && break
done

dir="$HOME/.claude/explain-selection/sessions"; mkdir -p "$dir"; chmod 700 "$dir"
umask 077
jq -n --arg sid "$sid" --arg cwd "$cwd" --arg tty "$tty" --arg pid "$pid" \
      --arg sock "${CLAUDE_CODE_MESSAGING_SOCKET:-}" --arg tok "${CLAUDE_CODE_MESSAGING_TOKEN:-}" \
      --arg name "${CLAUDE_SESSION_NAME:-}" \
      --arg tmux "${TMUX:-}" --arg pane "${TMUX_PANE:-}" \
   '{sessionId:$sid,cwd:$cwd,tty:$tty,pid:($pid|tonumber),socket:$sock,token:$tok,name:$name,
     tmux:$tmux,tmuxPane:$pane,at:now}' > "$dir/$pid.json"
```

`$pid` is the key everywhere: it is the socket filename and the `ps` handle. Pruning is by liveness (`kill -0`), not by trusting `SessionEnd` to always fire. `TMUX`/`TMUX_PANE` are inherited by the hook from the pane's environment, which makes multiplexer-aware targeting exact (§4.8).

Written for **bash 3.2.57** (what `/bin/bash` is on macOS): no `mapfile`, no associative arrays, no `${x^^}`. The pid-walk above was executed under 3.2 and resolves correctly.

**Security note to put in the README:** the registry stores the session's inbox token in a `0700` dir with `0600` files. Anyone who can read it can post turns into your session — the same privilege the `0600` socket already grants your own UID. No cross-user exposure, but it is a secret; `/explain-selection:doctor` asserts the permissions.

### 4.4 Delivery, concretely

**Mode B — inject into a running session** (verified working, **the primary path**)

```bash
sock=$(jq -r .socket "$reg"); tok=$(jq -r .token "$reg")
[[ -S $sock ]] || { sock="${XDG_RUNTIME_DIR:-/tmp}/cc-socks/$pid.sock"; [[ -S $sock ]] || sock="/tmp/cc-socks-$(id -u)/$pid.sock"; }
{ jq -nc --arg t "$tok" '{type:"auth",token:$t}'
  jq -nc --arg c "$msg" '{type:"user",message:{role:"user",content:$c}}'
} | nc -U "$sock"
```

- Build the whole payload *then* connect: the server closes a connection that sends no complete line within 30 s.
- `$msg` comes from a **prompt template file** shipped with the plugin. The template must inline the framing (`explain: <text>`) because a slash command inside an injected message arrives as inert text. The receiving session sees the full request, e.g.:
  `Explain the following code fragment:\n\n<text>\n\n(Relayed from my terminal selection by the explain-selection hotkey — this is my own request, answer it for me.)`
  Without that parenthetical the receiver reads it under peer-message rules ("a teammate asked") which is subtly wrong.
- Size cap ~1M chars; rapid bursts to one session are refused at the sender; identical repeats inside a short window are dropped.
- **Critical dependencies:** `SessionStart` hook + registry (carries the per-session `CLAUDE_CODE_MESSAGING_TOKEN` out to the hotkey script), `find-target.sh` (chooses which session receives the text), tmux pane tracking (§4.8). No Automation or Accessibility grant required.

**Mode A — new window** (fallback when no live session)

```bash
q=$(printf 'explain: %s' "$text" | head -c 4900 | jq -sRr @uri)
cwd=$(printf '%s' "$target_cwd" | jq -sRr @uri)
open "claude-cli://open?cwd=$cwd&q=$q"
```

- 5,000-char ceiling on `q`: truncate at ~4,800 and append `…[truncated]`, **or** (for big selections) write the text to `"$TMPDIR/explain-XXXX.txt"` and make the prompt `explain the text in <path>` — costs a file read and a permission prompt but is unbounded. Make it a config choice: `long_selection=truncate|tempfile`.
- Pre-fill `/explain-selection:explain <text>` instead of raw text if you want the skill's framing to apply in the new session (a pre-filled slash command does run once you press Enter).
- `find-target.sh` selects this path when `claude agents --json` returns zero interactive sessions.

### 4.5 Consequences of choosing B

Four design consequences that flow from making mode B the primary path:

1. **A skill cannot be invoked through B.** A slash command inside an injected message arrives as inert text and never executes — so the "explain" framing must be *inlined into the injected message text* by the injector, not delegated to the `/explain-selection:explain` skill. The skill stays useful for route A and for manual use, but the prompt template in the injector is what does the work for B. The plugin therefore ships a prompt template file (e.g. `templates/explain-prompt.txt`).

2. **Peer framing.** The message arrives flagged as coming from another Claude session, with guardrails telling the receiver it is not user approval. Word the template so the receiver understands it is relaying the human's own request. Example trailing parenthetical: `(Relayed from my terminal selection by the explain-selection hotkey — this is my own request, answer it for me.)` This overrides the peer-message framing and ensures the receiver treats it as a direct user question.

3. **Injecting into a busy session derails it.** An injected message is read between tool calls during an active turn, so "explain this" can land in the middle of unrelated work. Mitigations: (a) the template should instruct a brief answer and an explicit return to the prior task (e.g., *"Be concise. After answering, return to your previous task."*); (b) `claude agents --json` reports each session's `status` (`busy`/`idle`), so the injector can warn the user, hold the message until the session is idle, or prefer an idle session when several match the cwd. The plugin's default strategy: prefer idle, deliver to busy if none are idle, and log a warning.

4. **Context cost, but a much bigger payload.** B's text enters the conversation (that is the trade against C's `/btw`), so every injection adds to the session's context and costs tokens. However, B's size cap is ~1,000,000 characters versus A's 5,000, so B handles large selections (entire functions, stack traces, log files) far better than the fallback and needs no truncate-vs-tempfile policy. For enormous selections, the template can instruct Claude to read from a temp file rather than embedding the text inline.

### 4.6 Alternative: real `/btw`, not built

**Mode C** — terminal automation that literally types `/btw explain: …` into the TUI. Not built in the initial plugin, but documented for users who specifically want `/btw`'s zero-context-pollution property.

**iTerm2** (verified):
```bash
osascript <<EOF
tell application "iTerm2"
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if tty of s is "$devtty" then write s text "/btw explain: $esc" newline no
      end repeat
    end repeat
  end repeat
end tell
EOF
```
`write` is verified in `iTerm2.sdef`: direct parameter is the session, `text` is the string, `newline` is a boolean defaulting to **yes** — so `newline no` composes without submitting. Session `tty` is a read-only property. Targets the session **by tty**, so it works even if the window isn't frontmost, and needs only an Automation grant for iTerm2 (no Accessibility).

**tmux** — the best mode C available anywhere:
```bash
tmux send-keys -t "$pane" -l '/btw explain: the selected text …'   # -l = literal, no key-name parsing
# tmux send-keys -t "$pane" Enter                                  # only if auto_submit
```
No AppleScript, no Accessibility, no TCC prompt at all. Targets a specific pane whether or not it's active or attached.

**Other terminals:** Terminal.app `do script "…" in <tab>` (tabs expose `tty`, `selected`, `busy`) — whether `do script` reaches the pty of a *running foreground TUI* rather than a shell is **unverified**. Ghostty 1.2.3 has no AppleScript (`input text` arrives in 1.3.0) but its Shortcuts intent **Input Text to Terminal** does the same job. Universal fallback: `pbcopy` the composed line → `System Events` ⌘V → optional `Return` (needs Accessibility; save/restore the clipboard and guard on `changeCount`).

**Mode C notes:** **Single-line the text** (`tr '\n' ' '`, squeeze spaces, cap ~1,500 chars): a multi-line paste becomes a `[Pasted text #1]` placeholder, which is fine for a plain prompt but unreliable as a slash-command argument. **Default to `without newline`** (compose, don't submit). Auto-submit is opt-in — same philosophy as the deep link, and it removes the "autocomplete menu ate my Enter" failure mode.

### 4.7 Target selection (`find-target.sh`)

**Critical path for mode B**: chooses which session receives the injected text.

1. `claude agents --json` → live sessions (`kind=="interactive"`).
2. Exactly one → use it. (Covers the overwhelming majority of real use.)
3. Several → ask the frontmost terminal for its tty (`osascript`: iTerm2 `tty of current session of current window`, Terminal.app `tty of selected tab of front window`) and match on `ps -o tty=`. Ghostty exposes no scripting dictionary → skip to 4. **If any candidate has a `tmuxPane`, take the tmux branch in §4.8 instead** — under tmux the emulator tty belongs to the client, not to Claude Code.
4. Still ambiguous → filter by `status=="idle"` and prefer idle sessions. If still multiple or all busy, `osascript -e 'choose from list …'` showing `name — cwd (status)`, remembered for N minutes in `~/.claude/explain-selection/last-target`.
5. None → fall back to mode A with `cwd=$HOME` (or `repo=` if the frontmost window's cwd is known).

### 4.8 Running inside tmux (or any multiplexer)

**Mode B is unaffected** by tmux, which is a major advantage: the inbox is a filesystem path keyed by the Claude Code pid, and neither test that delivered a message had a controlling tty at all. tmux on macOS allocates ptys — it does not create a PID or mount namespace — so `/tmp/cc-socks/<pid>.sock` is exactly as reachable from inside or outside a pane, attached or **detached**. `claude agents --json` reads on-disk records, so tmux-hosted sessions list normally.

Two things do change:

1. **`ps -o tty=` now returns the *pane's* pty**, not the terminal tab's. So "ask iTerm2 for the frontmost tty, match it to a pid" silently fails under tmux — the emulator tty belongs to the tmux *client*, not to Claude Code. Fix by preferring the pane id the hook recorded:
   ```bash
   pane=$(tmux display-message -p '#{pane_id}' 2>/dev/null)          # active pane, e.g. %7
   grep -l "\"tmuxPane\":\"$pane\"" ~/.claude/explain-selection/sessions/*.json
   ```
   With no `$TMUX` in the hotkey script's environment, resolve the client first:
   ```bash
   tmux list-clients   -F '#{client_tty} #{client_session}'
   tmux list-panes -a  -F '#{pane_id} #{pane_tty} #{session_name} #{window_active} #{pane_active}'
   ```
   Match the frontmost emulator tty (AppleScript) to `client_tty`, then take that session's `window_active=1 pane_active=1` pane.
2. **Remote tmux is out of reach.** Over ssh to another host, the socket lives on that host's filesystem; mode B can't cross it (same reason a container can't reach the host's sessions). That's Remote Control / teleport territory, not this plugin's.

### 4.9 Skills

| Skill | Frontmatter | Purpose |
|---|---|---|
| `/explain-selection:explain` | `argument-hint: [text]`, `disable-model-invocation: true`, `user-invocable: true` | Receiving end for mode A and manual use. Body: "Explain the following fragment, which the user selected in their terminal. Identify what it is (log line, stack trace, shell command, code, error) and explain accordingly; be concise; don't modify files." + `$ARGUMENTS` |
| `/explain-selection:install` | `allowed-tools: Bash(…) Write` | Copies the Quick Action into `~/Library/Services`, writes `config.env` and the prompt template file, sets the shortcut, triggers + explains each TCC prompt, runs the smoke tests |
| `/explain-selection:doctor` | uses `` !`…` `` injection to gather facts before Claude reads them | Checks: handler app present; `~/Library/Services` entry + `defaults read pbs NSServicesStatus`; registry files vs `claude agents --json`; socket exists and is `0600`; **`crossSessionInbound` not set to `hold` or `refuse`**; **no session in `bypassPermissions` mode without a verified token**; `jq`/`nc` present; permissions granted; prints the exact fix for each failure |
| `/explain-selection:send` | `argument-hint: [session] [text]` | In-session use of mode B: "send this to my other session". Free once the plumbing exists |

**Prompt template:** The plugin ships `templates/explain-prompt.txt`, which is the actual framing used by mode B. The `/explain-selection:explain` skill cannot be invoked through an injected message, so the injector must inline the prompt. The template is user-editable and referenced by `config.env`.

`doctor` is where the `` !`command` `` dynamic-context feature pays off: the diagnosis is computed by shell before Claude sees the skill, so the answer is grounded and costs one turn. **Mode B failure modes it must check:** `crossSessionInbound` set to `hold` or `refuse` would silently break injection; a session in `bypassPermissions` mode holds messages from senders it cannot verify, which is exactly what the registry token prevents; the socket exists and is mode `0600`; the registry entry's pid is still alive (`kill -0 $pid`).

---

## 5. Capture layer (the macOS hotkey)

**Good news, verified:** all three terminals implement `NSServicesMenuRequestor` (`validRequestorForSendType:` / `writeSelectionToPasteboard:`) *and* expose `accessibilitySelectedText`. iTerm2 and Terminal.app at symbol level, Ghostty in source (`SurfaceView_AppKit.swift`). So a selection-receiving Quick Action works in all three, and so does an AX read.

**Ship #1 as the default; `install` offers #2–#4.**

1. **Automator Quick Action + Services shortcut** — zero dependencies, shipped as a `.workflow` bundle.
   "Workflow receives current **text** in **any application**" → `Run Shell Script` (pass input **to stdin**) → `"$PLUGIN/scripts/capture.sh"`. Copy to `~/Library/Services`. Automator 2.10 still supports this on 26.2 (verified).
   Assigning the key: `defaults write pbs NSServicesStatus -dict-add '"(null) - Explain selection - runWorkflowAsService"' '{key_equivalent = "@~e";}'` then `/System/Library/CoreServices/pbs -update`. Community practice, works but **takes effect only after apps relaunch** and `-flush` is reportedly not enough. Apple documents a ⌘-only restriction for bundled `NSKeyEquivalent`; for *user-assigned* shortcuts it's unverified — so `install` should write the key, then verify, then fall back to walking you to **System Settings › Keyboard › Keyboard Shortcuts › Services › Text**, which is the reliable path. ⌘⌥E is a safe choice either way.
2. **Ghostty's Shortcuts (App Intents) integration** — the best route on Ghostty ≥1.2, and it needs **no Accessibility and no Services**:
   Shortcuts.app: *Get Details of Terminal* → **Selected Text** → *Run Shell Script* → `capture.sh`; assign a keyboard shortcut in the shortcut's details. Requires `macos-shortcuts = ask` or `allow` in Ghostty config. The same intent set also gives *New Terminal* (with `command` + working directory) and *Input Text to Terminal* — i.e. Ghostty can deliver mode C natively too. (Ghostty AppleScript `input text` needs 1.3.0+; you're on 1.2.3.)
   Shortcuts caveats: enable *Allow Running Scripts* once (Settings › Advanced); a shortcut can be shipped signed (`shortcuts sign --mode anyone -i in -o out`) but **the key assignment is UI-only** — the `shortcuts` CLI has no setter.
3. **Native terminal keybindings** — what each terminal can and cannot do natively (all verified):
   - **iTerm2**: session variables `selection` and `selectionLength` exist, and the **Copy Interpolated String** action can evaluate `\(selection)` — but it writes to the clipboard only. **No key-binding action runs a shell command**; there is no "Run Command" key action, `Send Text` only expands `\n \e \a \t`, and `Invoke Script Function`'s built-ins are just `alert/count/get_string/move_tab_to_window`. Two usable native combinations:
     - `Sequence` → [`Copy Interpolated String` `\(selection)`, `Select Menu Item` "Explain selection"] — drives the Quick Action from an iTerm2 key binding without relying on the Services key equivalent. Untested; try it if #1's shortcut won't take.
     - Python API (verified, heavier): enable Settings › General › Magic › *Enable Python API*, download the Python runtime, drop an AutoLaunch script registering an `@iterm2.RPC`, bind it with `Invoke Script Function`; read the selection with `async_get_selection_text()`. Also gives `async_send_text()` for mode C.
     - Smart Selection rules *do* have a real "Run Command" action, but they fire on right-/cmd-click of a regex match, not from a hotkey — not applicable.
   - **Ghostty**: `write_selection_file:{copy|paste|open}` is the only selection-to-file action and takes **no arbitrary command** — `paste` pastes the temp-file *path* into the terminal, which is a cute way to hand a path to CC's prompt box but not a delivery mechanism. Use route #2 instead.
4. **Hammerspoon** — most robust, one `brew install --cask hammerspoon`, Accessibility prompt on first launch. `hs.hotkey.bind` → `hs.uielement.focusedElement():selectedText()`, falling back to `hs.eventtap.keyStroke({"cmd"},"c")` + `hs.pasteboard.changeCount()`, then `hs.task.new`. Works in every app including ones that skip Services. All APIs verified.

**Universal fallback inside `capture.sh`** (covers any app, any terminal): if stdin is empty, synthesize ⌘C via `osascript -e 'tell application "System Events" to keystroke "c" using command down'`, poll the pasteboard's `changeCount` for ≤300 ms, read `pbpaste`, restore the prior clipboard. Needs Accessibility for the calling process **and** Automation for System Events. Read the counter without Hammerspoon:

```bash
osascript -l JavaScript -e 'ObjC.import("AppKit"); $.NSPasteboard.generalPasteboard.changeCount'   # verified: returns an integer
```

`capture.sh` contract, so all four routes are interchangeable:

```
capture.sh [--mode newwindow|inject|btw] [--text -|<string>]
   stdin (or --text -)  →  selection; empty → clipboard path
   exit 0 always; user-visible errors go to `osascript -e 'display notification …'`
   every run appended to ~/.claude/explain-selection/log
```

---

## 6. Phases

| Phase | Work | Done when |
|---|---|---|
| **0. Smoke tests** (10 min, no code) | `nc -U` two-liner against a second session (mode B); confirm target resolution picks the right session with several open; `open "claude-cli://open?cwd=$HOME&q=explain%3A%20ls%20-la"` (mode A) | Message delivered to the intended session; fallback path verified |
| **1. Skeleton** | `claude plugin init explain-selection --with skills,hooks`; `explain` + `doctor` skills; `lib.sh`; prompt template; `claude plugin validate --strict` | `/explain-selection:explain foo` works; `--plugin-dir` loads clean; template exists |
| **2. Registry + target selection** | hooks (`SessionStart`, `SessionEnd`, `CwdChanged`), `register-session.sh`, `unregister-session.sh`, `find-target.sh` (including tmux pane tracking) | Registry entries created on session start, pruned on end; `find-target.sh` resolves to the right session with 3 sessions open, one idle and two busy; tmux pane correctly identified |
| **3. Mode B (primary)** | `deliver-inject.sh`, prompt template interpolation, framing logic, status filtering | Text injected into the intended session while it is mid-turn; prompt arrives correctly framed; idle session preferred when multiple candidates match |
| **4. Mode A (fallback)** | `deliver-newwindow.sh` + truncation/tempfile policy | `capture.sh --mode newwindow --text "$(pbpaste)"` opens a pre-filled window in the right cwd; fallback engages when no live session exists |
| **5. Hotkey + capture** | `.workflow` asset + `install` skill + TCC walkthrough, `capture.sh` (sanitize, cap length) | ⌘⌥E on a selection in iTerm2, Ghostty, Safari, VS Code → explanation appears in the running session or new window |
| **6. Ship** | `doctor` B-specific checks, `send` skill, `evals/`, README (including mode C as unbuilt alternative), marketplace repo | `claude plugin eval .` green; `doctor` catches `crossSessionInbound=refuse`; `/plugin marketplace add <you>/explain-selection` installs it |

**Mode C** is explicitly optional and unscheduled. The plugin documents it (§4.6) so users who want `/btw` can implement it themselves, but it is not part of the build.

---

## 7. Risks, limits, and open items

- **Mode B costs context, but handles large selections well**: the injected text becomes a real turn in the conversation, which enters the session's context and costs tokens. That is the trade against mode C's `/btw` (which this plugin does not build). However, B's ~1,000,000-char cap vastly exceeds A's 5,000, so it handles entire functions, stack traces, and log files far better than the fallback.
- **Injecting into a busy session derails it** (mode B): an injected message is read between tool calls, so "explain this" can land in the middle of unrelated work. Mitigations specified in §4.5: the prompt template instructs a brief answer and return to the prior task, and `find-target.sh` prefers idle sessions when multiple candidates match.
- **A slash command cannot be invoked through B** — commands in relayed messages arrive as inert text by design. The plugin ships a prompt template that inlines the "explain" framing; the `/explain-selection:explain` skill is for mode A and manual use only.
- **`q` ≤ 5,000 chars** (mode A fallback). Decide truncate vs. tempfile policy for large selections.
- **TCC prompts**: Automation (iTerm2/System Events) and, for the ⌘C fallback, Accessibility. They appear once, per-app, and cannot be granted from a script — `install` must walk you through them and `doctor` must detect the denied state. **Choosing mode B removes the Automation/Accessibility dependency from delivery** — the only remaining permission surface is the capture side.
- **Ghostty 1.2.3 has no AppleScript** (that lands in 1.3.0) and `ghostty +new-window` is GTK-only; from a script it's `open -na Ghostty.app --args -e <cmd> --working-directory=<abs>` (since 1.2.0 `-e` is not wrapped in `/bin/sh`). Its Shortcuts intents are the native route for both capture and mode C.
- **Selection in the TUI**: if you select text *inside* Claude Code's own output, mouse selection captures the hard-wrapped rendering. `/btw`'s `c` key (copy answer as raw Markdown) exists for that reason; note it in the README.
- **Resolved open items** (were §7 unknowns, now verified): iTerm2 has **no** key-binding action that runs a shell command — `Copy Interpolated String` is the only one that evaluates `\(selection)`, and it only writes the clipboard, so the non-Python native trick is `Sequence` → [copy interpolated string, `Select Menu Item`]. Ghostty's `write_selection_file` takes only `copy|paste|open`, never a command. Apple's ⌘-inclusive restriction is documented for bundled `NSKeyEquivalent`; for `pbs key_equivalent` extra modifiers appear accepted in practice but treat ⌘-inclusive as the safe assumption, and expect to relaunch apps for the change to register.
- **Still unverified, cheap to settle in Phase 0**: `do script … in <tab>` reaching a TUI's pty; `pbs -update` behavior on 26.2 with a real service installed; a live `AXSelectedText` read (the research probe wasn't AX-trusted, so this is source-level only).

---

## 8. One-liners worth keeping

```bash
# B: inject into a live session (pid from `claude agents --json`) — THE CHOSEN PATH
{ jq -nc --arg t "$TOK" '{type:"auth",token:$t}'
  jq -nc --arg c "explain: $T" '{type:"user",message:{role:"user",content:$c}}'
} | nc -U "/tmp/cc-socks/$PID.sock"

# A: new window, prompt pre-filled (fallback when no live session)
open "claude-cli://open?cwd=$(printf %s "$PWD" | jq -sRr @uri)&q=$(printf 'explain: %s' "$T" | jq -sRr @uri)"

# C: compose /btw in the frontmost iTerm2 session without submitting (alternative, not built)
osascript -e 'tell application "iTerm2" to write current session of current window text "/btw explain: '"$T"'" newline no'
```
