The review subagent should be Fable at xhigh effort level. It should not receive the context of the chat. Here is the prompt it receives:

Review the changes against main. The goal of the change is:

<here goes succinct content of the change>

  in particular check that the solution:
  - achieves the goal
  - does not introduce expensive or excessive db requests
  - does not introduce unnecessary computational complexity
  - does not break existing behavior
  - there are no paths that swallow errors
  - has appropriate test coverage
  - ground all your findings in the code lines with references to specific files and line numbers
  - if there are no blockers - say so