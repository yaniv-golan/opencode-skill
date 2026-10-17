# opencode-skill — agent instructions

A Claude Code skill that delegates coding tasks to the OpenCode CLI and supervises the result.
Claude plans, briefs, reviews and lands; OpenCode edits. Forked from
[pcx-wave/opencode-skill](https://github.com/pcx-wave/opencode-skill) (MIT) and rewritten.
This is a **public repository**.

## Layout

A Claude Code marketplace containing one plugin, `opencode-delegate`, with one skill, `opencode`
(invoked as `/opencode-delegate:opencode`).

| Path | What it is |
|---|---|
| `.claude-plugin/marketplace.json` | Marketplace manifest (`opencode-delegate-marketplace`). |
| `opencode-delegate/.claude-plugin/plugin.json` | Plugin manifest. |
| `opencode-delegate/skills/opencode/SKILL.md` | The skill: the orchestration workflow Claude follows. Ships to users. |
| `opencode-delegate/skills/opencode/scripts/delegate.py` | The only script. Stdlib Python; every OpenCode interaction goes through it. Ships to users. |
| `evals/opencode/evals.json` | Test prompts for the skill. Outside the plugin on purpose, so it never ships. |
| `evals/harness/` | cowork-harness protocol scenarios for those prompts, fixtures, and `run.sh` (live runs only; no cassettes). |
| `skill-packager.json`, `VERSION`, `VERSIONING.md` | Packaging metadata and the version contract. |
| `README.md`, `CHANGELOG.md`, `LICENSE` | User-facing docs; LICENSE carries both the upstream and the fork copyright. |
| `docs/internal/` | Local-only notes (gitignored). Never reference it from tracked files. |
| `CLAUDE.local.md`, `.worktreeinclude` | Per-developer Claude instructions (gitignored), and the list of gitignored files Claude Code copies into new worktrees. |

Only `opencode-delegate/` ships. Claude Code copies an installed plugin into its plugin cache, and
refreshes it only when `plugin.json`'s version changes.

## Versioning

The version appears in five places and must match everywhere: `skill-packager.json` (source of
truth), `VERSION`, `.claude-plugin/marketplace.json` (`metadata.version`), `plugin.json`, and the
SKILL.md frontmatter (`metadata.version`). See `VERSIONING.md`. Any change users should receive
needs a bump and a `CHANGELOG.md` entry. Check consistency with skill-packager's `validate`.

## Invariants — do not weaken without an explicit decision from the maintainer

These are the reason the fork exists. Each one was found broken or missing upstream, and each fix
was verified against a real OpenCode server.

1. **Isolation.** Every task runs in its own git worktree on branch `opencode/<task>`, or, for a
   snapshot of uncommitted work, on the private ref `refs/opencode-delegate/tasks/<task>` so
   `git push --all` can't publish it. Never point OpenCode at the user's working tree. Never suggest `git checkout .` or anything that discards
   the user's work.
2. **One shared server.** All runs attach (`opencode run --attach`) to a single `opencode serve`.
   Separate `opencode run` processes share a SQLite DB and fail with `database is locked`.
3. **Ownership.** The server is password-protected, and the script reuses only a server that
   accepts its password *and* rejects unauthenticated requests. Never reuse a server it didn't start.
4. **Default-deny policy.** A run uses `--auto`, which approves every `ask`, so the policy must be an
   allowlist: `bash` with `"*": "deny"`, plus `external_directory: deny`. The script refuses to run
   otherwise. Never use or document `--dangerously-skip-permissions`.
5. **Check what is enforced, not what is written.** Before each run the script resets the server's
   per-directory config cache (`POST /instance/dispose`) and checks the merged config the server
   reports (`GET /config?directory=…`). The server caches config per directory; without the reset, an
   edited policy is silently ignored.
6. **A run is over when the script says so.** On timeout or exit, abort every busy session in the
   task's worktree. A session still queued when its client dies otherwise keeps running and edits
   the worktree after the run was reported.
7. **Minimal server environment.** `opencode serve` starts with `server_env()`'s allowlist, never a
   copy of the caller's environment, and with the bundled `opencode-plugin/scrub-env.js` loaded via
   `OPENCODE_CONFIG_CONTENT`; a run requires that plugin's fresh heartbeat. Every command OpenCode
   runs inherits the server's environment.
8. **The user's checkout is written only by `apply`.** Snapshots use a temporary index; `apply`
   is a separate, explicit command that touches the working tree only (the index only with
   `--3way`) and changes nothing on conflict. Per-attempt commits use a bot identity with git hooks
   disabled, because hooks would run repo code with the user's permissions.
9. **Evidence, not claims.** Changed files come from `git status` before and after the run. Run-log
   entries are measured values only; never write estimated or invented numbers into
   `runs.jsonl`.

## Code rules (`delegate.py`)

- Python 3.9+ standard library only. No third-party packages, no shell-outs to GNU-only tools
  (`timeout`, GNU `date`, `sed -i` without a suffix). It must run on stock macOS and Linux.
- Keep the CLI non-interactive with structured plain-text output. The documented exit codes
  (0 ok, 1 refused, 2 wrote nothing, 3 timeout, 4 error, 5 syntax, 6 apply conflict, 7 a `--check` failed or a file outside `--only` changed, 8 `wait`: still running) are a contract that `SKILL.md`
  depends on. Change both together, or not at all.
- Keep it one file. A second script needs a reason the first can't absorb.
- Pass prompts and paths as argv lists, never through a shell. `--setup` and `--check` are the
  only intentional `shell=True` uses; both run commands the *orchestrator* chose, not OpenCode.
  A `--check` runs after OpenCode may have edited the code it calls, so it gets the server's
  minimal environment, never the caller's.

## Skill rules (`SKILL.md`)

- Keep it under 19,900 characters, measured with `wc -m` (not lines). After compaction, Claude
  re-attaches a skill truncated to that size. Move whole sections to `references/` before
  trimming meaning.
- Reach the script only through the `${CLAUDE_SKILL_DIR}` line in `SKILL.md`. Never put that
  variable in a shell command or in a `references/` file; it is substituted only in `SKILL.md` text.
- The `description` field is a trigger, not a summary. Changes to it affect when the skill loads.
- Free model IDs change without notice. Name one default (`DEFAULT_MODEL` in `delegate.py`) and
  point readers to `delegate.py models` instead of listing models in prose.

## Claims about OpenCode

OpenCode changes fast and its docs lag the binary. Any statement in this repo about OpenCode
behaviour (flags, permission semantics, API endpoints, config keys) must be verified against a
real run on a stated version, and say which version. Tested baseline: **OpenCode 1.19.3**.
Known moving part: 1.19's schema marks `permission` deprecated in favour of an ordered
`permissions` list. The script refuses the new format until its semantics are verified. Don't
"support" it from the schema alone.

## Testing

There is no unit-test suite; changes are verified by smoke runs. **Always isolate test runs** from
any real installation:

```bash
export OPENCODE_DELEGATE_HOME=$(mktemp -d /tmp/ocd-test.XXXXXX) OPENCODE_DELEGATE_PORT=4098
```

Keep test state and throwaway repos out of macOS's per-user temp dir (`/var/folders/…`, where a
bare `mktemp -d` lands): OpenCode 1.19.3 hangs at startup when its working directory is there.

Use a throwaway git repo with a policy from `delegate.py init`. Exercise what you touched, and
always re-check:

- refusals that must not create anything: empty prompt, bad slug, non-git dir, missing or weak
  policy, unknown model
- a happy-path run, a run that hits a denied command, and two runs in parallel
- `--timeout` short enough to fire while the request is still queued, then confirm with
  `server status` (0 active sessions) and `git status` in the worktree a minute later
- a server you started yourself on the test port must be refused, not reused
- `diff` (vs the recorded base, `--last`), `list`, `remove` (dirty refuses, clean succeeds), `report`
- `--from-working-tree`: main checkout's status, `.git/index` hash, staged diff and stash list
  identical before and after; secret-named untracked file refused
- `apply`: `--check`, clean apply, conflict (exit 6, file unchanged), already-applied
- snapshot task: worktree detached, private ref follows each attempt, and `git push --all` to a
  scratch bare remote does not carry the ref or the snapshot's blobs
- `--check` (a passing and a failing check → exit 7, FAIL output shown) and `--only` (an
  out-of-scope change → exit 7); both reused by the next attempt of the same task
- `--add-only` extends the saved `--only` list (`[scope]` shows it); `OPENCODE_DELEGATE_PASS_ENV`
  set on a run reaches its `--check`
- policy integrity: a changed untracked (or gitignored) worktree copy is replaced; a differing
  committed copy is refused, and runs with `--allow-worktree-policy`; OpenCode editing the policy
  → exit 7 `POLICY MODIFIED`, even when that is its only change
- snapshot task with an untracked policy: the snapshot leaves it out; a later main-checkout edit is picked up
- `land`: refuses `--commit` when a task file has the user's own changes (file untouched),
  commits only the task's files, leaves other staged work staged, removes the task
- `run --detach` returns once live; `wait` reports the result once, a question, a run that ended
  before `wait` started, and a SIGKILLed broker as CRASHED (sessions aborted, client stopped);
  SIGTERM to a run → interrupted attempt, 0 active sessions; a second run of a live task refused
- server lock: while a run is live, `server stop` and a run that needs a server restart are refused
  (exit 1); both succeed once it ends or is SIGKILLed; `server stop --force` still stops it
- isolation: a fresh server's effective config has no `mcp` from the user's global config; a
  task cannot see the global ~/.claude/CLAUDE.md or Claude skills, but sees the repo's AGENTS.md;
  a loadable `.opencode/` plugin refuses without `--allow-opencode-dir`
- messaging: `tell` before a run (in the brief) and during one (delivered once); `ask_orchestrator`
  → `wait` returns it → `answer` → tool result; a
  forged or unsigned envelope is neutralised; parallel `hook` calls deliver each message once;
  `pair` lets a peer message arrive as a `<peer-message>`, and an unpaired send is refused

Validate the skill after any `SKILL.md` change. These validators come from the `skill-creator-plus`
plugin; run them from that skill's directory:

```bash
python -m scripts.quick_validate <repo>/opencode-delegate/skills/opencode
python -m scripts.check_portability <repo>/opencode-delegate/skills/opencode --target claude-code
```

Stop the test server (`delegate.py server stop` with the same env) and remove its state dir when done.

## Git and publishing

- Work on a named branch. `upstream` is pcx-wave's repo; never push to it.
- In a clone with an `upstream` remote, `gh` targets pcx-wave's repo by default. Run
  `gh repo set-default yaniv-golan/opencode-skill` once, or pass `--repo` to every `gh` command.
- Stage files by name. Don't use `git add -A`, `-u` or `.` unless you've confirmed every line of
  `git status` is in scope.
- Commit messages and tracked files must not contain AI session URLs, `Co-Authored-By` lines for
  AI tools, local machine paths, or references to `docs/internal/`.
- Don't commit, push, tag or publish unless asked.
- Keep the upstream attribution (README, licence) intact.
