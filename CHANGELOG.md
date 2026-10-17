# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/);
versions follow [Semantic Versioning](https://semver.org/).

## [2.1.0] - 2026-10-17

### Added
- `run --from-working-tree`: start a new task from a snapshot of the main checkout's current files
  (uncommitted edits and untracked, non-ignored files), taken through a temporary index so the
  user's index, files and stash are untouched. Lists the untracked files it includes and refuses
  secret-looking names unless `--allow-secret-files`.
- `apply`: put a task's changes into the main checkout's working tree as unstaged edits, with
  `--check` (dry run), refusal on any conflict (exit 6, nothing changed), opt-in `--3way`, and
  detection of a task that was already applied.
- Each run's changes are committed on the task branch as `opencode attempt N` (bot identity, git
  hooks and signing disabled), so retries never lose work; `diff --last` shows the latest attempt.
- Per-task metadata records the task's base, so `diff` and `apply` measure OpenCode's changes, not
  the user's snapshot; `list` shows base, attempt commits, uncommitted changes and applied state.

### Changed
- The skill tells Claude to read every changed test, config, script and build file before running
  checks, because checks execute that code outside any OpenCode policy.

### Fixed
- `remove --delete-branch` checks first and changes nothing when the branch holds attempts that
  were neither applied nor merged; an applied branch can now be deleted without `--force`.

## [2.0.2] - 2026-10-17

### Security
- The skill now tells Claude to stop and ask before delegating in a repo that has a `.opencode/`
  directory in it or above it. OpenCode loads plugins, tools, skills, agents and commands from there
  into the shared server, outside the `opencode.json` policy. Interim guidance; an enforced fix is
  being designed together with sandboxing.

## [2.0.1] - 2026-10-17

### Security
- The shared server now starts with a minimal environment instead of a copy of the caller's, so
  secrets in the shell Claude runs in (API keys, tokens) no longer reach OpenCode's shells. Extra
  variables are passed only when named in `OPENCODE_DELEGATE_PASS_ENV`.
- A bundled server-level OpenCode plugin blanks `OPENCODE_SERVER_PASSWORD` in every command
  OpenCode runs. A run is refused unless the plugin wrote a fresh load heartbeat for its worktree,
  and an idle server started without the current plugin is restarted automatically.

### Fixed
- A failed or slow server start no longer overwrites the record of a running server, which left an
  unreachable server holding the port. The server is recorded only once healthy, a busy port is
  detected by TCP connect instead of an HTTP timeout, and a live-but-unresponsive server is reported
  instead of being started twice.
- A run refused after its worktree was created now removes that worktree and branch.

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
