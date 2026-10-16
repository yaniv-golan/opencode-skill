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

1. **Isolation.** Every task runs in its own git worktree on branch `opencode/<task>`. Never point
   OpenCode at the user's working tree. Never suggest `git checkout .` or anything that discards
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
7. **Evidence, not claims.** Changed files come from `git status` before and after the run. Run-log
   entries are measured values only; never write estimated or invented numbers into
   `runs.jsonl`.

## Code rules (`delegate.py`)

- Python 3.9+ standard library only. No third-party packages, no shell-outs to GNU-only tools
  (`timeout`, GNU `date`, `sed -i` without a suffix). It must run on stock macOS and Linux.
- Keep the CLI non-interactive with structured plain-text output. The documented exit codes
  (0 ok, 1 refused, 2 wrote nothing, 3 timeout, 4 error, 5 syntax) are a contract that `SKILL.md`
  depends on. Change both together, or not at all.
- Keep it one file. A second script needs a reason the first can't absorb.
- Pass prompts and paths as argv lists, never through a shell. `--setup` is the one intentional
  `shell=True`, and it runs commands the *orchestrator* chose, not OpenCode.

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
export OPENCODE_DELEGATE_HOME=$(mktemp -d) OPENCODE_DELEGATE_PORT=4098
```

Use a throwaway git repo with a policy from `delegate.py init`. Exercise what you touched, and
always re-check:

- refusals that must not create anything: empty prompt, bad slug, non-git dir, missing or weak
  policy, unknown model
- a happy-path run, a run that hits a denied command, and two runs in parallel
- `--timeout` short enough to fire while the request is still queued, then confirm with
  `server status` (0 active sessions) and `git status` in the worktree a minute later
- a server you started yourself on the test port must be refused, not reused
- `diff`, `list`, `remove` (dirty refuses, clean succeeds), `report`

Validate the skill after any `SKILL.md` change. These validators come from the `skill-creator-plus`
plugin; run them from that skill's directory:

```bash
python -m scripts.quick_validate <repo>/opencode-delegate/skills/opencode
python -m scripts.check_portability <repo>/opencode-delegate/skills/opencode --target claude-code
```

Stop the test server (`delegate.py server stop` with the same env) and remove its state dir when done.

## Git and publishing

- Work on a named branch. `upstream` is pcx-wave's repo; never push to it.
- Stage files by name. Don't use `git add -A`, `-u` or `.` unless you've confirmed every line of
  `git status` is in scope.
- Commit messages and tracked files must not contain AI session URLs, `Co-Authored-By` lines for
  AI tools, local machine paths, or references to `docs/internal/`.
- Don't commit, push, tag or publish unless asked.
- Keep the upstream attribution (README, licence) intact.
