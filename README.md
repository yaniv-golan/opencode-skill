# opencode-delegate

[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-plugin-F97316)](https://docs.anthropic.com/en/docs/claude-code/plugins)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Packaged with Skill Packager](https://img.shields.io/badge/Packaged_with-Skill_Packager-8B5CF6?style=flat-square)](https://github.com/yaniv-golan/skill-packager-skill)

**Claude orchestrates. OpenCode codes. Claude reviews. You decide what lands.**

A Claude Code skill that hands coding tasks to the [OpenCode](https://opencode.ai) CLI, typically
on a free model from OpenCode Zen. Claude splits the work, writes a self-contained brief for each
task, supervises the run, reviews the diff, and runs your project's real checks. OpenCode does the
editing.

Forked from [pcx-wave/opencode-skill](https://github.com/pcx-wave/opencode-skill) (MIT) and
rewritten. The changes from upstream:

| Upstream | This fork |
|---|---|
| Runs in your working tree; `git checkout .` to undo | One git worktree + branch (`opencode/<task>`) per task; your checkout is never touched |
| `--dangerously-skip-permissions` (approve everything) | `--auto` gated by a required default-deny `opencode.json` policy |
| One `opencode run` process per task; concurrent runs fail with `database is locked` | All runs attach to one shared, password-protected `opencode serve`; parallel tasks work |
| Bash + GNU `timeout` (missing on macOS) | Single stdlib Python script; works on macOS and Linux |
| Kills only the client on timeout | Aborts the server-side session |
| Changed files by mtime over the whole tree | `git status` before/after, OpenCode's changes only |
| Auto-mode via a rule appended to global `~/.claude/CLAUDE.md` | Opt-in per project, in that project's `CLAUDE.md` |
| Hard-coded, now-retired default model | `opencode/deepseek-v4.1-flash-free`, validated against the live model list |

## Requirements

- OpenCode CLI ≥ 1.19 (`brew install opencode`); tested on 1.19.3
- Python 3.9+, git ≥ 2.25
- Claude Code

## Install

From your terminal:

```bash
claude plugin marketplace add https://github.com/yaniv-golan/opencode-skill
claude plugin install opencode-delegate@opencode-delegate-marketplace
```

Or from within a Claude Code session:

```
/plugin marketplace add yaniv-golan/opencode-skill
/plugin install opencode-delegate@opencode-delegate-marketplace
```

Restart Claude Code (or run `/reload-plugins`) after installing or updating, so it loads the new
version. Updates arrive with `claude plugin update opencode-delegate@opencode-delegate-marketplace`.

To work on the skill itself, add a local clone as the marketplace instead:
`/plugin marketplace add /path/to/opencode-skill`.

## Set up a repository

`<plugin>` below is the installed plugin directory. Claude resolves it for you; to run the script
yourself, find it with `find ~/.claude/plugins -path '*opencode-delegate/skills/opencode/scripts/delegate.py'`.

Delegation is refused until the repo has an `opencode.json` that denies unlisted shell commands:

```bash
python3 <plugin>/skills/opencode/scripts/delegate.py init /path/to/repo \
  --allow "pnpm check" --allow "pnpm test:unit"
```

Allow only the exact commands OpenCode needs to check its own work. Commit the file.

If the repo pins a toolchain (e.g. `.nvmrc`), start the shared server with that toolchain first on
PATH, because OpenCode's shell commands inherit the server's environment:

```bash
OPENCODE_DELEGATE_PATH_PREPEND=~/.nvm/versions/node/v24.18.0/bin \
  python3 <plugin>/skills/opencode/scripts/delegate.py server start
```

## Use

In Claude Code:

```
/opencode-delegate:opencode add input validation to the export dialog
```

Or ask Claude to "have OpenCode do it". To make delegation the default for one project, add a
line saying so to that project's `CLAUDE.md`.

Script commands (`delegate.py --help`): `server start|stop|status`, `models`, `init`, `run`,
`diff`, `apply`, `list`, `remove`, `report`.

### Working on uncommitted changes

`run --from-working-tree` starts a task from your current files, including uncommitted edits and
new files git isn't ignoring, without touching your checkout. When it's done, `apply --check` then
`apply` puts OpenCode's changes into your working tree as unstaged edits. `apply` refuses, and
changes nothing, if they conflict with edits you made in the meantime. Each attempt is a commit on
the local `opencode/<task>` branch. **Don't push `opencode/*` branches:** a snapshot-based one
contains your uncommitted work.

## Safety model

- `--auto` approves every permission that is not explicitly denied, so the policy must be an
  allowlist: `"bash": {"*": "deny", ...}` and `"external_directory": "deny"`. The script refuses to
  run without them.
- The policy is not a sandbox. OpenCode can edit any file in its worktree, including a test it is
  allowed to run. The worktree isolation and Claude's review are the real safety net; use a
  container if you need containment.
- Free models are offered for a limited time and have different data terms. Some log or train on
  inputs, so check before using one on private code.

## License

MIT, following upstream.
