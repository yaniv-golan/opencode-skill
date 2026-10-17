# What the script guarantees, in detail

Read when a task's isolation, attempts, server or evidence matter.

- **Isolation.** `run --task <slug>` creates a worktree in the script's state dir
  on branch `opencode/<slug>` from the main checkout's `HEAD`, `--base`, or — with
  `--from-working-tree` — a snapshot of the user's current files (uncommitted and untracked,
  non-ignored), taken without touching their index, files or stash. When that snapshot differs from
  `HEAD`, the task's commits live on the private ref `refs/opencode-delegate/tasks/<slug>` (detached
  worktree) instead of a branch, so `git push --all` never publishes the user's uncommitted files; a
  clean tree gives an ordinary `opencode/<slug>` branch. Re-running the same `--task`
  reuses that worktree, so a retry builds on the previous attempt.
- **Attempts are commits.** After each run the script commits OpenCode's changes on the task's
  branch or private ref as `opencode attempt N` (bot identity, git hooks disabled). Retries never lose earlier work, and
  `diff --last` shows only the latest attempt.
- **One server.** All runs attach to a single password-protected `opencode serve` on
  127.0.0.1:4096 (started on demand). Separate `opencode run` processes share a SQLite DB and fail
  with `database is locked` when run concurrently; through the server they don't.
- **Policy gate.** The run is refused unless the worktree's `opencode.json` denies unlisted shell
  commands (`"bash": {"*": "deny", …}`) and edits outside the worktree (`external_directory: deny`).
  Runs use `--auto`, which approves anything merely set to `ask`, so an allowlist is the only shape
  that holds. The server's per-directory config cache is reset before every run.
- **Bounded.** Wall-clock `--timeout` (default 1800 s); on expiry the server-side session is aborted,
  not just the client.
- **Evidence.** Changed files are computed from `git status` before/after (OpenCode's changes only),
  syntax-checked (.py/.js/.mjs/.cjs/.json/.sh/.bash), and logged to the run log.
- **All task state goes through the script.** `list` shows each task's worktree path, attempts,
  uncommitted changes, last run outcome and whether a run is live; `diff` shows its changes and
  `report` past runs. The state dir's location varies (`OPENCODE_DELEGATE_HOME`): never read or
  search its files directly.

