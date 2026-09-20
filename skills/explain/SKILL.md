---
name: explain
description: Explain a fragment the user selected in their terminal. Receiving end of the new-window fallback; also for manual use.
argument-hint: [text]
disable-model-invocation: true
user-invocable: true
---

Explain the following fragment, which the user selected in their terminal. Identify what it is (log line, stack trace, shell command, code, error message) and explain it accordingly. Be concise. Do not modify any files.

$ARGUMENTS
