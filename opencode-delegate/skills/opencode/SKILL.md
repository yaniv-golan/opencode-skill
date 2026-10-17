---
name: opencode
description: >
  Delegate coding work to the OpenCode CLI (free models such as DeepSeek V4.1 Flash via OpenCode Zen)
  while Claude plans, writes the brief, supervises and reviews. Each task runs in its own git worktree
  and branch through one shared `opencode serve`, under a default-deny command policy, so several
  tasks can run in parallel without touching the user's checkout. Use when the user types
  /opencode or /opencode-delegate:opencode, asks to "have OpenCode do it", "delegate to opencode", "let the free model code this",
  or when the project's CLAUDE.md says coding is delegated to OpenCode. Also covers setting a repo up
  for delegation (opencode.json policy), choosing the OpenCode model, and reporting past runs.
argument-hint: "<task description>"
metadata:
  version: 2.1.0
---

# OpenCode delegation

Claude is the orchestrator: understand the request, split it into atomic tasks, write a
self-contained brief per task, launch OpenCode, watch it, review the diff, run the project's real
checks, and report. OpenCode does the editing. Its tokens are free; yours are not, so spend yours on
the brief and the review, not on re-doing its work.

**Running this skill's scripts.** Use the absolute path this file was loaded with:

    python3 ${CLAUDE_SKILL_DIR}/scripts/delegate.py <subcommand> [args]

Do not type `$CLAUDE_SKILL_DIR` into a shell command — it is a load-time text substitution, not an
environment variable, and expands to nothing in a shell. Read the resolved path out of this line
and pass it along verbatim, including to any sub-agent. `delegate.py --help` lists every subcommand.

## What the script guarantees (so you don't re-implement it)

- **Isolation.** `run --task <slug>` creates `~/.local/state/opencode-delegate/worktrees/<repo>/<slug>`
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
  syntax-checked (.py/.js/.mjs/.cjs/.json/.sh/.bash), and logged to `~/.local/state/opencode-delegate/runs.jsonl`.

## Step 0 — Is the repo set up?

Find the repo root (`git rev-parse --show-toplevel`). Read its agent rules (`AGENTS.md`,
`CLAUDE.md`, `CONTRIBUTING.md`) — they bind you, and OpenCode reads `AGENTS.md` itself.

**If the repo, or any folder above it, contains a `.opencode/` directory, stop and ask the user
before delegating.** OpenCode loads plugins, tools, skills, agents and commands from it into the
shared server, where they run outside the `opencode.json` policy. Nothing in the script checks for
this yet.

If there is no `opencode.json` at the root, delegation will be refused. Create one:

    python3 ${CLAUDE_SKILL_DIR}/scripts/delegate.py init <repo> --allow "pnpm check" --allow "pnpm test:unit"

Add `--allow` only for the exact project commands OpenCode needs to self-verify (lint, typecheck,
unit tests). Prefer exact commands to wildcards; never allow `node *`, `python *`, `npx *`, `sh`,
`curl`, `rm` or `git commit/push` — any of those hands OpenCode an unrestricted shell. Show the user
the file, and ask before committing it (repo rules on commits apply). Until it is committed, the
script copies the uncommitted file into each new worktree.

## Step 1 — Decide what to delegate

| Situation | Action |
|---|---|
| One obvious edit, location known, ≤ ~10 lines | Do it yourself; a delegation round-trip costs minutes |
| Non-trivial logic in 1–3 files, one goal | One delegation |
| More than 3 files, several steps, or a migration | Split into atomic tasks; delegate each |
| Independent tasks (different files/concerns) | Separate `--task` slugs, run in parallel |
| Design decisions, ambiguous requirements, security-sensitive code | Settle them yourself first; delegate only the mechanical part |

Dependent tasks run in sequence on the **same** `--task` (the worktree carries forward) — check the
diff between steps before launching the next.

## Step 2 — Write the brief

OpenCode sees only the brief, `AGENTS.md`, and the files. Make it self-contained:

```
Context: <stack, one line>. Repo rules: follow AGENTS.md.
Files: <exact paths to change>; read <path> first for conventions.

TASK: <one imperative objective>

CONSTRAINTS:
- <what must not change / break>
- <exact signature if a function is defined or called: `export function sub(a, b): number`>

VERIFY: run `<an allowlisted check command>` and confirm it passes;
        use the grep tool (not shell grep) to find "<symbol>" in <file>.
Run each command on its own (no `&&`, `;` or pipes). Do not commit.
Make the edits now; do not just describe them.
```

One objective per brief. Name the files. Give a VERIFY step OpenCode can actually run under the
policy: an allowlisted command, or OpenCode's own grep/read tools, which the policy allows. Shell
`grep`, `cat` or `echo` are denied unless allowlisted, and a denied command wastes turns. Write long briefs to a file
and pass `--prompt-file`.

## Step 3 — Launch

    python3 ${CLAUDE_SKILL_DIR}/scripts/delegate.py run --repo <repo> --task <slug> --prompt-file <brief.md> [--timeout 1800] [--model …] [--setup "<cmd>"]

- `--task`: short kebab-case slug, unique per independent task (`fix-date-parse`).
- `--from-working-tree` (new task only): when the task depends on the user's uncommitted work.
  It lists every untracked file it includes and refuses secret-looking untracked names (`.env*`;
  `.pem/.key/.p12/.pfx/.kdbx/.keystore/.jks` files; `id_rsa`/`id_dsa`/`id_ecdsa`/`id_ed25519`
  keys; `credentials*`, `.netrc`, `.npmrc`, `.pypirc`) unless `--allow-secret-files`; never pass
  that without asking the user.
- `--setup`: a command **the script** (not OpenCode) runs once in a new worktree — e.g.
  `"pnpm install --frozen-lockfile --offline"` — because a fresh worktree has no `node_modules` or
  other untracked build state.
- Free models queue: even a trivial task usually takes 2–5 minutes and sometimes 15–20. Launch with your Bash tool's
  background option and wait for the completion notice rather than polling; launch parallel tasks
  together.

## Step 4 — Read the result

The script streams `[tool] target` lines with elapsed seconds, then a summary. Exit codes of `run`:

| Exit | Outcome | What to do |
|---|---|---|
| 0 | `OK` — changes made, syntax clean | Review (Step 5) |
| 2 | `WROTE_NOTHING` | Read OpenCode's last `[opencode]` text: it may have refused, asked a question, or only described the change. Sharpen the brief; don't silently do it yourself |
| 3 | `TIMEOUT` — session aborted | `diff` to see partial work; split the task or raise `--timeout` |
| 4 | `ERROR` — model/server error | Retry once; if repeated, try another model (`models`) |
| 5 | `SYNTAX_ERRORS` | Re-delegate on the same `--task` with the error text, or fix if trivial |
| 1 | Refused before delegating | Read the message (policy, model, slug, setup). Fix the cause; **never pass `--unsafe-policy`** to get past a policy refusal unless the user explicitly tells you to |

Red flags in the stream: `[DENIED]` (OpenCode tried a command the policy blocks — usually it should
not need it; widen the allowlist only for a legitimate project check, and tell the user),
`[WARN] … read 5 times` (circling), `COMMITS CREATED BY OPENCODE` (policy hole — tell the user).

## Step 5 — Review like a reviewer, not a rubber stamp

    python3 ${CLAUDE_SKILL_DIR}/scripts/delegate.py diff --repo <repo> --task <slug>

Read the whole diff (the task's base to now; add `--last` for the latest attempt only). Check it
against the brief and the repo rules: scope creep, deleted tests, weakened assertions, invented
data, edits to files outside the brief.

**Before running any check, read every changed test, config, script, `package.json`, lockfile and
build file in the diff.** Running checks executes that code with your permissions, outside any
OpenCode policy (OpenCode is not sandboxed yet). If a change could run something the brief didn't
ask for — a network call, a new dependency, a postinstall, a file write outside the repo — don't run
the checks; report it to the user.

Then run the project's real checks yourself **inside the worktree** (`cd` into the path printed as
`worktree`) — OpenCode's own VERIFY is a claim, not evidence. Report failed, skipped and unrun
checks distinctly.

## Step 6 — Iterate (max 3 attempts per task)

Re-run with the same `--task` and a brief that names what is wrong with the current diff ("the
current diff does X; change it to Y; keep Z"). Don't restate the whole task — the worktree already
has the partial work. After 3 failed attempts, stop and ask the user. If OpenCode got most of the
way, finishing a small remainder yourself is fine — say so in the report.

## Step 7 — Land it (the user decides)

Report to the user before landing anything:

```
OpenCode finished <task> — <one-line summary>
Model <model>, <duration>s, attempts <n>
Files: <path> (+a/-d) …
Checks: <command> PASS | FAIL (<why>) | NOT RUN (<why>)
Concerns: <anything you would flag in review>
Worktree: <path>  Commits: opencode/<slug> or refs/opencode-delegate/tasks/<slug>
```

With the user's go-ahead, land it in one of two ways:

- **`apply` (default; required for `--from-working-tree` tasks)** puts the task's changes into the
  user's working tree as unstaged edits, on top of whatever they have there now. Dry-run first:

      python3 ${CLAUDE_SKILL_DIR}/scripts/delegate.py apply --repo <repo> --task <slug> --check
      python3 ${CLAUDE_SKILL_DIR}/scripts/delegate.py apply --repo <repo> --task <slug>

  `apply` first commits any edits still uncommitted in the worktree (as `manual edits before
  apply`). Exit codes of `apply`: 0 applied (or `--check` clean), 2 nothing to apply or already
  applied, 6 conflicts. Exit 6 means nothing was changed: re-run the task with `--from-working-tree` on a
  new `--task`, or ask before `--3way` (it touches the index and can leave conflict markers). The
  user then reviews and commits as they normally would.
- **Merge or cherry-pick `opencode/<slug>`**, only for tasks based on a commit, following the repo's
  rules. Never merge a snapshot-based branch: its base commit contains the user's uncommitted work.

Clean up afterwards:

    python3 ${CLAUDE_SKILL_DIR}/scripts/delegate.py remove --repo <repo> --task <slug> [--delete-branch]

`remove` refuses while the worktree has uncommitted changes (`--force` discards them — only on the
user's say-so). `remove --delete-branch` also refuses, and removes nothing, while the task's attempts
were neither applied nor merged. Task branches and refs are local working state: don't push them, and never use
`git push --mirror` in a repo with snapshot tasks (it pushes every ref, including
`refs/opencode-delegate/*`). `remove --delete-branch` deletes the branch or private ref too.

## Models

Default: `opencode/deepseek-v4.1-flash-free` (override per run with `--model`, or set
`OPENCODE_DELEGATE_MODEL`). `delegate.py models` lists what the server offers right now; free
models are "limited time" and the list changes, so check it rather than trusting any hard-coded name.

- Free models change and so do their data terms: some are zero-retention, others log or train on
  what you send. Before using one on private code, check its terms at https://opencode.ai/zen (as
  of OpenCode 1.19.3, DeepSeek V4.1 Flash and GLM-5.3-Flash were listed as zero-retention, and
  NVIDIA's Nemotron trial endpoints as logging everything).
- `report` compares models on your own runs; prefer that to benchmarks.

## Gotchas

- **Never use `--dangerously-skip-permissions`.** OpenCode 1.19 does not document it but silently
  accepts it, so you cannot tell what it does. The script uses `--auto` plus the policy.
- **The policy is not a sandbox.** OpenCode can edit any file in the worktree, including a test
  script it is then allowed to run. Isolation (worktree) and your review are the real safety net.
- **Where a task starts.** By default from the main checkout's committed `HEAD`, so uncommitted work
  is invisible to OpenCode. `--base <ref>` starts from another commit; `--from-working-tree` starts
  from a snapshot of the user's current files and must be landed with `apply`. Both apply to a new
  task only.
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

## Auto-delegation for one project

To make a project delegate coding by default, add a line to **that project's** `CLAUDE.md` (never the
global one), e.g. `Coding tasks in this repo are delegated to OpenCode via the opencode skill;
Claude plans, briefs, reviews and lands.` Ask the user before editing it.

## Reporting

    python3 ${CLAUDE_SKILL_DIR}/scripts/delegate.py report [--since 7] [--project NAME] [--fails]

Per-model runs, outcomes, median duration and tokens, from measured runs only.
