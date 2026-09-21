---
name: doctor
description: Check the explain-selection installation, the live sessions and the inbox policy, and explain how to fix what is wrong
disable-model-invocation: true
user-invocable: true
---

# Doctor output

!`"${CLAUDE_PLUGIN_ROOT}/bin/explain-selection" doctor 2>&1`

Read the output above. Summarise the failed and warned checks for the user in one short list, each with its fix line. If the output is missing or says the command was not found, say the plugin's runtime is not installed and point to `/explain-selection:install`. Do not run install yourself. If everything is ok say so in one line.
