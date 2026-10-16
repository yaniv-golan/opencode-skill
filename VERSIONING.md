# Versioning

[Semantic Versioning](https://semver.org/). The version must be identical in all five places
below; `skill-packager.json` is the source of truth.

1. `skill-packager.json` — `"version"`
2. `VERSION`
3. `.claude-plugin/marketplace.json` — `metadata.version`
4. `opencode-delegate/.claude-plugin/plugin.json` — `"version"`
5. `opencode-delegate/skills/opencode/SKILL.md` — `metadata.version` in the frontmatter

Claude Code updates an installed plugin only when `plugin.json`'s version changes, so bump it for
any change users should receive.

## Release

1. Update the five locations and add a `CHANGELOG.md` entry.
2. Check consistency: `python3 -m skill_packager validate <repo>` (from the skill-packager
   plugin's `scripts/` directory).
3. Commit the changed files by name, tag `vX.Y.Z`, and push the branch and the tag.
