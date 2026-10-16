# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/);
versions follow [Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-10-16

Fork of [pcx-wave/opencode-skill](https://github.com/pcx-wave/opencode-skill) at `7b06df5`, rewritten
and packaged as the `opencode-delegate` Claude Code plugin.

### Added
- Claude Code plugin and marketplace packaging (`opencode-delegate@opencode-delegate-marketplace`).
- One git worktree and branch (`opencode/<task>`) per task; the user's checkout is never touched.
- A single shared, password-protected `opencode serve`; parallel tasks no longer fail with
  `database is locked`.
- Required default-deny `opencode.json` policy, checked against the config the server actually
  enforces; `delegate.py init` writes one.
- Server-side session abort on timeout and on exit, including sessions still queued.
- `OPENCODE_DELEGATE_PATH_PREPEND` for repos that pin a toolchain, with a warning on `.nvmrc`
  mismatch.
- `--setup` for per-worktree dependency installs, run by the script rather than OpenCode.
- `models`, `diff`, `list`, `remove` and `report` subcommands.

### Changed
- `opencode-delegate` (Bash, requiring GNU `timeout`) and `delegate-report` replaced by one
  stdlib Python script that runs on stock macOS and Linux.
- Runs use `--auto` with the policy instead of `--dangerously-skip-permissions`.
- Default model `opencode/deepseek-v4.1-flash-free`, validated against the server's live model list.
- Changed files come from `git status` before and after the run, not file timestamps.

### Removed
- Global auto-mode (a rule appended to `~/.claude/CLAUDE.md`) and the five toggle skills.
  Auto-delegation is now opted into per project, in that project's `CLAUDE.md`.
- Estimated "manual completion" entries in the run log.
