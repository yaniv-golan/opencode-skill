# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/);
versions follow [Semantic Versioning](https://semver.org/).

## [2.1.0] - 2026-10-17

### Added
- `run --from-working-tree`: start a new task from a snapshot of the main checkout's current files
  (uncommitted edits and untracked, non-ignored files), taken through a temporary index so the
  user's index, files and stash are untouched. Lists the untracked files it includes and refuses
  secret-looking names unless `--allow-secret-files`. The snapshot task's commits live on the
  private ref `refs/opencode-delegate/tasks/<task>` (detached worktree), not a branch, so
  `git push --all` / `--branches` never publish the user's uncommitted files.
- `apply`: put a task's changes into the main checkout's working tree as unstaged edits, with
  `--check` (dry run), refusal on any conflict (exit 6, nothing changed), opt-in `--3way`, and
  detection of a task that was already applied.
- Each run's changes are committed on the task branch as `opencode attempt N` (bot identity, git
  hooks and signing disabled), so retries never lose work; `diff --last` shows the latest attempt.
- Per-task metadata records the task's base, so `diff` and `apply` measure OpenCode's changes, not
  the user's snapshot; `list` shows base, attempt commits, uncommitted changes and applied state.
- Messaging between Claude and a task's OpenCode agent, with no daemon: each `run` is its task's
  broker.
  - `tell` queues a message: it opens the next attempt's brief, or reaches a live session mid-task,
    delivered once.
  - `answer` replies to a task's question.
  - `inbox` reads the task messages addressed to this Claude session.
  - `agents` shows each task's queued messages and whether its run is live.
  - `pair` lets two tasks of one repo message each other.
- A bundled OpenCode plugin gives the task three tools: `message_orchestrator`,
  `ask_orchestrator` (waits for the answer) and `send_message` (paired tasks only).
  - Each run has a private localhost endpoint with a one-time bearer token, and a limit of 5
    messages of at most 4 KB.
  - Messages are wrapped in envelopes signed with the run's token. The plugin neutralises unsigned
    or forged envelopes, and escapes envelope tags in tool output.
  - A peer's message has its own envelope and never counts as an instruction from the orchestrator.
- Plugin hooks (PostToolUse, UserPromptSubmit) deliver a task's messages to the orchestrating
  Claude session as data, never as user instructions.
  - Subagents are skipped.
  - Read, deliver and acknowledge happen in one locked step, so hooks running in parallel deliver
    each message once.
- `run --check CMD` (repeatable): the script runs each check in the worktree after OpenCode
  finishes, with the server's minimal environment, and reports PASS/FAIL.
- `run --only PATH` (repeatable; a path, directory or glob): changes outside these paths are
  reported.
- Both options are saved on the task and reused by later attempts. A failed check or an
  out-of-scope change returns the new exit code 7.
- `run` appends the standing rules to every brief, so briefs no longer repeat them:
  - follow AGENTS.md;
  - one shell command at a time;
  - no commits;
  - make the edits now;
  - plus the scope and the checks, when given.
- `land`: apply a task, optionally commit exactly its files (`--commit -m …`, with the user's own
  identity and hooks), then remove the task.
  - It refuses to commit when any of those files has the user's own uncommitted changes.
  - Other staged work stays staged.

- `run --detach` starts a run as its own process and returns once it is live. `wait --repo R
  [--task T] [--max SECS] [--stream]` waits in the foreground and returns on a task's question or
  message, a finished run (its result block), a crashed run (its sessions aborted, its orphaned
  client stopped), or after `--max` (exit 8 = still running). This works without background shells,
  which Claude Cowork and one-shot sessions don't have. `--stream` prints one line per event for
  Claude Code's Monitor tool.
- `attach --repo R --task T [--fork]` opens OpenCode's own viewer on a task's live session in the
  user's terminal.
- `list` shows each task's last run outcome and whether a run is live.
- Every run writes its own log, `<state dir>/logs/<repo>/<task>/<run id>.log`.

### Changed
- The skill tells Claude to read every changed test, config, script and build file before running
  checks, because checks execute that code outside any OpenCode policy.
- The skill now covers the cost of Claude's own time: it spends Claude's output tokens on briefs,
  review and decisions, and delegates even small fixes.
- The skill now covers waiting for long tasks:
  - wake once, when the run ends or a question arrives;
  - launch with `run --detach` and wait in the foreground with `wait`, never with background shells;
  - take worktree paths from `list` and past runs from `report`, never by guessing the state dir.
- Secondary gotchas moved to `references/gotchas.md`, and model data terms to `references/models.md`.

### Fixed
- Tolerate OpenCode server stalls: while a session is busy the server can stop answering HTTP for
  tens of seconds. API calls now retry for up to two minutes, a stalled server is waited out
  instead of refused, and `server status` reports a stall instead of "not running".
- Default `--timeout` raised to 1800 s; free-model runs sometimes take 15–20 minutes.
- The skill's docs: where tasks start (`--base`, `--from-working-tree`), use OpenCode's grep tool
  rather than shell grep, never pass `--unsafe-policy` to get past a refusal, the exact secret-name
  list, private refs only when the snapshot differs from `HEAD`, `apply`'s exit codes and its
  pre-apply commit, and model data terms pointing to OpenCode Zen.
- `remove --delete-branch` checks first and changes nothing when the branch holds attempts that
  were neither applied nor merged; an applied branch can now be deleted without `--force`.
- Server start and restart are serialised across processes, and `server stop` waits until the old
  server has exited, so runs started in parallel no longer race each other into a restart.
- Heartbeat and plugin-token files are keyed by the resolved path. Before this, a worktree reached
  through a symlink (macOS `/var` → `/private/var`, or a symlinked checkout) was refused, and its
  messaging was silently off.
- The server starts from `/`, not from the caller's directory. OpenCode 1.19.3 hangs at startup
  when its working directory is under the macOS per-user temp dir.
- Server start waits up to 90 s, on a deadline.
- **Privacy:** the delegate server no longer reads the user's global OpenCode config, which can add
  MCP servers and plugins outside the policy. It also no longer passes on the user's own Claude
  Code material: OpenCode had been putting the global `~/.claude/CLAUDE.md` into every task's prompt
  and offering skills from `~/.claude/skills` and `~/.agents/skills`. A server started by an older
  version restarts when it is idle.
- The policy check refuses any enabled MCP server unless `--allow-mcp NAME` is passed.
- The script refuses a run when the task's worktree or `~/.opencode` holds extensions OpenCode would
  load (plugins, tools, agents, commands, modes, skills) unless `--allow-opencode-dir` (remembered
  per task until they change). A run that creates such files fails the gate (exit 7).
- A run that is signalled (SIGTERM, SIGHUP, SIGINT) now stops OpenCode, aborts its server sessions,
  commits what it left as an "interrupted" attempt and logs the run. Before this, OpenCode kept
  editing after the script exited.
- The task lease is a file lock: a stale lease after a crash or reboot never reads as live, a second
  run of the same task is refused, and `apply`, `remove` and `land` refuse while a run is live.
- `server stop` no longer waits two minutes on a server that has already exited.

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

[2.1.0]: https://github.com/yaniv-golan/opencode-skill/compare/v2.0.2...v2.1.0
[2.0.2]: https://github.com/yaniv-golan/opencode-skill/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/yaniv-golan/opencode-skill/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/yaniv-golan/opencode-skill/releases/tag/v2.0.0
