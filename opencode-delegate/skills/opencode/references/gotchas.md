# More gotchas

Read when a run behaves unexpectedly: environment, toolchains, policy caching, stalls and timeouts.

- **What OpenCode's shells can see.** The server starts with a minimal environment (PATH, HOME,
  locale, proxy and toolchain basics, plus `OPENCODE_*` settings), because every command OpenCode
  runs inherits it. Pass anything else explicitly with `OPENCODE_DELEGATE_PASS_ENV=NAME,…`; set on
  a `run`, it also reaches that run's `--check` commands (which get the same minimal environment). A
  bundled server plugin also blanks the server password inside every OpenCode shell; the run is
  refused if that plugin did not load. This is risk reduction, not isolation: any process running as
  the user can still read the password from the state dir or from the server's own environment
  (`ps -E`), and any credential files.
- **Pinned toolchains.** OpenCode's shell commands run with the *server's* PATH, shared by every
  repo. If a repo pins Node (`.nvmrc`) the script warns on mismatch, naming the nvm bin dir when
  that version is installed; fix it with `server stop`, then start again with
  `OPENCODE_DELEGATE_PATH_PREPEND=<pinned node bin dir>` set (it also applies to `--setup` and
  `--check`). A `run` without the variable reuses the running server's prepend, including when the
  script restarts the server itself.
- **The policy check reads what the server enforces**, not just the file: after the cache reset it
  fetches the merged config (global + project). OpenCode 1.19's schema marks `permission` deprecated
  in favour of an ordered `permissions` list; if that format ever appears, the script refuses rather
  than guess its semantics.
- **Don't run bare `opencode run` in parallel**, and don't start your own `opencode serve` on the
  same port — always go through `delegate.py`.
- **Editing `opencode.json` mid-task:** edit the main checkout's file. It takes effect on the next
  `run` (the script resets the server's cache). An uncommitted policy's worktree copy is the
  script's own: each `run` replaces a differing copy with the main checkout's, so edits to the
  worktree's copy are discarded. A policy committed in the task's base that differs from the main
  checkout's is refused unless `--allow-worktree-policy`. If OpenCode edits the policy during a
  run, the run ends `GATE_FAILED` with `POLICY MODIFIED`.
- **Chained commands are checked piece by piece.** `node --check x.js && echo OK` is denied when
  `echo` is not allowlisted; OpenCode then burns turns retrying. The brief template says "one command
  at a time" for this reason.
- **A timed-out run is fully stopped.** If the client is killed while the request is still queued,
  the server-side session would otherwise keep running and edit the worktree after the run was
  reported (observed). The script aborts every busy session in the worktree on exit and before each run.
- **Free models share one usage limit.** When it is used up, OpenCode holds the session in a silent
  retry until the reset (observed: midnight UTC), and the client waits without output. The script
  checks the session's status every 15 seconds and ends the run as `ERROR` with `MODEL UNAVAILABLE`
  and the reset time, for a usage limit or any retry more than two minutes away. Switching to
  another free model doesn't help; the limit covers them all, and every task on the machine.
- **The server can stall.** While a session is busy, the OpenCode server sometimes stops answering
  for tens of seconds. The script waits up to two minutes before giving up; `server status` says
  "not answering right now" during one. Don't `server stop` a stalled server unless it stays stuck.
- `server stop` ends every active session; `server status` shows how many are running.
- **Keep the script path in a variable, not the whole command.** zsh does not split unquoted
  variables, so `P="python3 /…/delegate.py"; $P list` fails; `S=/…/delegate.py; python3 $S list`
  works in every shell.
- **Secret-looking files in a snapshot.** `--from-working-tree` lists every untracked file it
  includes and refuses these names unless `--allow-secret-files`: `.env*`;
  `.pem/.key/.p12/.pfx/.kdbx/.keystore/.jks` files; `id_rsa`/`id_dsa`/`id_ecdsa`/`id_ed25519`
  keys; `credentials*`, `.netrc`, `.npmrc`, `.pypirc`.
- **Making a project delegate by default.** Add a line to **that project's** `CLAUDE.md` (never the
  global one), e.g. `Coding tasks in this repo are delegated to OpenCode via the opencode skill;
  Claude plans, briefs, reviews and lands.` Ask the user before editing it. That makes every coding
  task cost the orchestration turns, small ones included.
