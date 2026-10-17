# opencode-delegate

[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-plugin-F97316)](https://code.claude.com/docs/en/plugins)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Packaged with Skill Packager](https://img.shields.io/badge/Packaged_with-Skill_Packager-8B5CF6?style=flat-square)](https://github.com/yaniv-golan/skill-packager-skill)

**Claude orchestrates. OpenCode codes. Claude reviews. You decide what lands.**

`opencode-delegate` is a Claude Code plugin that hands coding tasks to the
[OpenCode](https://opencode.ai) CLI, typically on a free model from OpenCode Zen. Claude splits the
work, writes a self-contained brief for each task, supervises the run, reviews the diff, and runs
your project's real checks. OpenCode does the editing. This repository is named `opencode-skill`
after the project it was forked from; the plugin you install is `opencode-delegate`.

See [CHANGELOG.md](CHANGELOG.md) for what's in each version.

## How it differs from upstream

Forked from [pcx-wave/opencode-skill](https://github.com/pcx-wave/opencode-skill) (MIT) and
rewritten:

| Upstream | This fork |
|---|---|
| Runs in your working tree; `git checkout .` to undo | One git worktree per task; your checkout is never touched |
| `--dangerously-skip-permissions` (approve everything) | `--auto` gated by a required default-deny `opencode.json` policy |
| One `opencode run` process per task; concurrent runs fail with `database is locked` | All runs attach to one shared, password-protected `opencode serve`; parallel tasks work |
| Only committed code | Optionally starts from your uncommitted files and lands the result with a checked `apply` |
| Bash + GNU `timeout` (missing on macOS) | Single stdlib Python script; works on macOS and Linux |
| Kills only the client on timeout | Aborts the server-side session |
| Changed files by mtime over the whole tree | `git status` before/after, OpenCode's changes only |
| Auto-mode via a rule appended to global `~/.claude/CLAUDE.md` | Opt-in per project, in that project's `CLAUDE.md` |
| Hard-coded, now-retired default model | A free default model, checked against the live model list |
| Fire and forget | Claude and a running task message each other; the script runs your checks and flags changes outside the task's files |

## Requirements

- macOS or Linux (Windows is not supported)
- [OpenCode CLI](https://opencode.ai) ≥ 1.19 (`brew install opencode`); tested on 1.19.3
- Python 3.9+ and git ≥ 2.31
- Claude Code

## Install, update, uninstall

```bash
claude plugin marketplace add yaniv-golan/opencode-skill
claude plugin install opencode-delegate@opencode-delegate-marketplace
```

Or in a Claude Code session: `/plugin marketplace add yaniv-golan/opencode-skill`, then
`/plugin install opencode-delegate@opencode-delegate-marketplace`.

Then run `/reload-plugins` in open sessions (or `/reload-plugins --force` if it warns about the
prompt cache), or start a new session.

**Updates don't arrive on their own.** Auto-update is off by default for third-party marketplaces.
Update with `claude plugin update opencode-delegate@opencode-delegate-marketplace`, or turn on
auto-update for this marketplace in `/plugin` → Marketplaces.

**Uninstall** with `claude plugin uninstall opencode-delegate@opencode-delegate-marketplace`
(removing the marketplace with `claude plugin marketplace remove opencode-delegate-marketplace`
also uninstalls it). That doesn't delete:
- `~/.local/state/opencode-delegate/` (task worktrees, server record, run log);
- `opencode/<task>` branches and `refs/opencode-delegate/` refs in repos you delegated in.

## Quickstart

In a Claude Code session inside your repository:

```
/opencode-delegate:opencode add input validation to the export dialog
```

Or ask Claude to "have OpenCode do it". What happens next:

1. **First time in a repo,** Claude creates an `opencode.json` policy, shows it to you, and asks
   before committing it. Delegation is refused without one.
2. Claude briefs OpenCode, runs it in a separate worktree, and reads the diff.
3. Claude runs your checks and reports back: files changed, what passed, and anything it would flag.
4. **Nothing lands until you say so.** The result waits in its worktree until you ask Claude to
   apply or merge it.

While a task runs, Claude can correct it mid-task, and OpenCode can stop and ask Claude a question.
Claude answers only what the brief left open, and asks you before changing the scope.

If the task depends on your uncommitted work, say so: Claude starts it from a snapshot of your
current files, and later puts the changes into your working tree as unstaged edits (or reports a
conflict and changes nothing).

To make delegation the default for one project, add a line saying so to that project's `CLAUDE.md`.

## Safety model

Read this before using it on code you care about.

- **A policy, not a sandbox.** Runs use OpenCode's `--auto`, which approves everything that isn't
  explicitly denied, so the policy must be an allowlist (`"bash": {"*": "deny", …}` and
  `"external_directory": "deny"`). The script refuses to run without one, and checks the policy the
  server actually enforces. But OpenCode can still edit any file in its worktree, including a test
  or build script that an allowed check command then runs. Code OpenCode writes runs as you.
- **What's isolated:** each task gets its own worktree under `~/.local/state/opencode-delegate/worktrees/`,
  so your checkout is untouched until you apply. Only `apply` writes to your checkout (working tree
  only; it changes nothing on conflict).
- **What OpenCode's shells can see:** a minimal environment (PATH, HOME, locale, proxy and toolchain
  basics), not your shell's. Secrets such as API keys don't reach them unless you pass them with
  `OPENCODE_DELEGATE_PASS_ENV`. The server password is blanked inside OpenCode's shells, but it's
  stored in `~/.local/state/opencode-delegate/server.json`, which any process running as you can read.
- **Repo-supplied OpenCode config:** a `.opencode/` directory in the repo or any folder above it is
  loaded into the shared server, outside the policy. Claude stops and asks before delegating in such
  a repo; the script doesn't check this yet.
- **Uncommitted work:** a snapshot task copies your uncommitted and untracked (non-ignored) files into
  its worktree. Secret-looking untracked names (`.env*`, keys, certificates, credential files) are
  refused unless you allow them. Its commits live on a private ref, so `git push --all` won't publish
  them, but `git push --mirror` would.
- **Model data terms:** free models are offered for a limited time, and some log or train on what you
  send. Check [OpenCode Zen](https://opencode.ai/zen) before using one on private code.

- **Messages between Claude and a task** travel through a localhost endpoint that only that run
  can reach (a one-time token), at most 5 per run of up to 4 KB each. They are signed, and the
  task's plugin neutralises forged ones, for example text in a file that imitates a message.
  Claude treats a task's message as data to review, never as an instruction from you.
- **Checks and landing:** checks you ask the script to run (`--check`) run code OpenCode may have
  edited, so they get the same minimal environment as OpenCode's shells. `land --commit` commits
  only the task's files, as you, with your git hooks, and refuses if you have your own
  uncommitted changes in those files.

To report a security problem, see [SECURITY.md](SECURITY.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| "refusing to delegate: unsafe or missing OpenCode policy" | Create one: `delegate.py init <repo> --allow "<your check command>"`, review it, commit it |
| "port 4096 is held by a process this script did not start" | Stop that process, or set `OPENCODE_DELEGATE_PORT` to a free port |
| "repo pins Node … but the server's shell has …" | `delegate.py server stop`, then start a run with `OPENCODE_DELEGATE_PATH_PREPEND=<pinned node bin dir>` set |
| `database is locked` | You ran `opencode run` directly in parallel; go through `delegate.py`, which shares one server |
| `apply` exits 6 | Your files changed where OpenCode's did. Nothing was touched; re-run the task from your current state |
| `run` exits 7 | A `--check` failed, or OpenCode changed a file outside `--only`; the run output lists which |
| Claude asks about a `.opencode/` directory | It loads into the server outside the policy; remove or review it before delegating |

## Advanced: using `delegate.py` directly

Claude normally runs the script for you. To run it yourself, find it with
`find ~/.claude/plugins -path '*opencode-delegate/skills/opencode/scripts/delegate.py'`.
Subcommands (`delegate.py --help` for details): `server start|stop|status`, `models`, `init`, `run`,
`diff`, `apply`, `land`, `list`, `remove`, `report`, and for messaging `tell`, `answer`, `inbox`,
`agents`, `pair` (`hook` is called by the plugin's Claude Code hooks).

### The policy `init` writes

`delegate.py init <repo> --allow "pnpm check" --allow "pnpm test:unit"` writes:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "edit": "allow",
    "read": "allow",
    "external_directory": "deny",
    "webfetch": "deny",
    "bash": {
      "*": "deny",
      "git status*": "allow",
      "git diff*": "allow",
      "git log*": "allow",
      "git show*": "allow",
      "ls*": "allow",
      "pwd": "allow",
      "node --check *": "allow",
      "pnpm check": "allow",
      "pnpm test:unit": "allow"
    }
  }
}
```

Entries ending in `*` are globs. Add only exact check commands. Never allow interpreters or
wildcards on them (`node *`, `python *`, `npx *`, `pnpm exec *`), `sh`, `curl`, `rm`, or
`git commit`/`git push`: each one gives OpenCode an unrestricted shell or a way out.

### Environment variables

| Variable | Effect |
|---|---|
| `OPENCODE_DELEGATE_MODEL` | Default model (else the built-in free default; `delegate.py models` lists what's offered) |
| `OPENCODE_DELEGATE_PORT` | Port of the shared server (default 4096) |
| `OPENCODE_DELEGATE_HOME` | State directory (default `~/.local/state/opencode-delegate`) |
| `OPENCODE_DELEGATE_PATH_PREPEND` | Directories put first on PATH for the server, and so for every command OpenCode runs, e.g. a pinned Node's `bin`. Read at server start: `server stop` first to change it |
| `OPENCODE_DELEGATE_PASS_ENV` | Comma-separated extra variables to pass to the server. **Every name listed is copied into every OpenCode shell**, so never list secrets |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Acknowledgements

- [pcx-wave/opencode-skill](https://github.com/pcx-wave/opencode-skill): the original skill this
  project was forked from and rewritten (MIT).
- [OpenCode](https://opencode.ai): the coding agent this plugin drives.
- [skill-creator-plus](https://github.com/yaniv-golan/skill-creator-plus): used to write, validate
  and evaluate the skill (`quick_validate`, `check_portability`, the trigger-eval workflow).
- [skill-packager](https://github.com/yaniv-golan/skill-packager-skill): used to package this repo
  as a Claude Code plugin and marketplace, and to check version consistency (`validate`).

Neither tool ships in the plugin; they're development tools only.

## License

MIT. A fork of [pcx-wave/opencode-skill](https://github.com/pcx-wave/opencode-skill); see
[LICENSE](LICENSE).
