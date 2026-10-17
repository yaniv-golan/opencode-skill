# More gotchas

Read when a run behaves unexpectedly: environment, toolchains, policy caching, stalls and timeouts.

- **What OpenCode's shells can see.** The server starts with a minimal environment (PATH, HOME,
  locale, proxy and toolchain basics, plus `OPENCODE_*` settings), because every command OpenCode
  runs inherits it. Pass anything else explicitly with `OPENCODE_DELEGATE_PASS_ENV=NAME,…`. A
  bundled server plugin also blanks the server password inside every OpenCode shell; the run is
  refused if that plugin did not load. This is risk reduction, not isolation: any process running as
  the user can still read the password from the state dir or from the server's own environment
  (`ps -E`), and any credential files.
- **Pinned toolchains.** OpenCode's shell commands run with the *server's* PATH, shared by every
  repo. If a repo pins Node (`.nvmrc`) the script warns on mismatch; fix it with
  `server stop`, then start again with `OPENCODE_DELEGATE_PATH_PREPEND=<pinned node bin dir>` set
  (it also applies to `--setup`).
- **The policy check reads what the server enforces**, not just the file: after the cache reset it
  fetches the merged config (global + project). OpenCode 1.19's schema marks `permission` deprecated
  in favour of an ordered `permissions` list; if that format ever appears, the script refuses rather
  than guess its semantics.
- **Don't run bare `opencode run` in parallel**, and don't start your own `opencode serve` on the
  same port — always go through `delegate.py`.
- **Editing `opencode.json` mid-task** takes effect on the next `run` (the script resets the server's
  cache), but a worktree keeps its own copy: edit the worktree's file, or the warning will tell you
  which copy is enforced.
- **Chained commands are checked piece by piece.** `node --check x.js && echo OK` is denied when
  `echo` is not allowlisted; OpenCode then burns turns retrying. The brief template says "one command
  at a time" for this reason.
- **A timed-out run is fully stopped.** If the client is killed while the request is still queued,
  the server-side session would otherwise keep running and edit the worktree after the run was
  reported (observed). The script aborts every busy session in the worktree on exit and before each run.
- **The server can stall.** While a session is busy, the OpenCode server sometimes stops answering
  for tens of seconds. The script waits up to two minutes before giving up; `server status` says
  "not answering right now" during one. Don't `server stop` a stalled server unless it stays stuck.
- `server stop` ends every active session; `server status` shows how many are running.
