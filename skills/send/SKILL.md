---
name: send
description: Send a message to another running Claude Code session through its inbox socket.
argument-hint: [session] [text]
allowed-tools: Bash(explain-selection:*)
---

Send the user's message to another running Claude Code session through its inbox socket.

1. List the live sessions with `explain-selection sessions`. If `explain-selection` is not on PATH, run `"${CLAUDE_PLUGIN_ROOT}/bin/explain-selection" sessions` instead. Each output line has the form `pid status kind registered|unregistered label cwd`, where `kind` is `interactive` (a session a person is looking at) or `background` (an unattended job); both kinds can be sent to.
2. Pick the session that matches the user's description by name (label), directory (cwd) or pid. If several sessions match, or none does, ask the user which session to use. Do not guess.
3. Post the message verbatim, with the text on stdin via a heredoc:

   ```sh
   explain-selection send --pid <pid> --text - <<'EOF'
   <message text>
   EOF
   ```

4. Report the command's output to the user. If the exit code is not 0, relay the stderr text as well.
