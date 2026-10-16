@AGENTS.md

## Claude Code specifics

- **The installed plugin is a copy.** Claude Code copies an installed plugin into
  `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` and runs that copy; editing this repo
  changes nothing for an installed plugin until its version is bumped and it is updated
  (`claude plugin update opencode-delegate@opencode-delegate-marketplace`).
- **While iterating, load the plugin from the repo instead:** start the session with
  `claude --plugin-dir <repo>/opencode-delegate`. Before trusting a test, make sure which copy of
  `SKILL.md` and `delegate.py` the session actually loaded; the skill prints its own path in the
  `${CLAUDE_SKILL_DIR}` line.
- **Validate packaging** with `claude plugin validate <repo>` as well as skill-packager's
  `validate` (see `VERSIONING.md`).
- **To test the skill end to end,** use the eval prompts in `evals/opencode/evals.json` with the
  `skill-creator-plus` plugin, against a throwaway repo, never against a real project.
