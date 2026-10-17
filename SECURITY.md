# Security policy

## Reporting a vulnerability

Please **don't open a public issue** for a security problem. Report it privately:

- through GitHub: **Security → Report a vulnerability** on this repository, or
- by email to yaniv@golan.name.

Include the plugin version (`claude plugin list`), the OpenCode version (`delegate.py server status`
prints it), your OS, and the smallest steps that show the problem. You'll get an acknowledgement
within a week.

## In scope

This plugin: `SKILL.md`, `delegate.py` and its bundled OpenCode plugin. For example:

- a way for OpenCode to run a command, or write a file, that the policy should have blocked;
- the policy check passing while the server enforces something weaker;
- a secret reaching OpenCode's shells (environment, server password);
- the user's checkout, index or uncommitted work being changed without an explicit `apply`;
- a snapshot of uncommitted work being published (pushed) by the plugin's own behaviour;
- a task continuing to run after the script reported it finished or timed out.

## Out of scope

- Vulnerabilities in OpenCode itself, Claude Code, or the model providers: report those upstream.
- The documented limits in the README's safety model. The policy is not a sandbox; code OpenCode
  writes runs as you; a `.opencode/` directory loads outside the policy; `git push --mirror`
  publishes snapshot refs. Reports that show these limits are worse than documented are in scope.

## Supported versions

Only the latest release gets fixes.
