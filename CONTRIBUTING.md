# Contributing

Thanks for helping. Issues and pull requests are welcome. Contributions are accepted under the
MIT license (see [LICENSE](LICENSE)); there's no CLA.

## Read first

- [AGENTS.md](AGENTS.md): the project's rules and the invariants that must not be weakened (it's
  written for coding agents, but it's the source of truth for humans too).
- [VERSIONING.md](VERSIONING.md): the version appears in five places; any change users should
  receive needs a bump in all five and a [CHANGELOG.md](CHANGELOG.md) entry.

## Testing a change

There's no unit-test suite: changes are verified by smoke runs against a real OpenCode server.
Never test against your real state directory, port, or a project you care about:

```bash
export OPENCODE_DELEGATE_HOME=$(mktemp -d) OPENCODE_DELEGATE_PORT=4098
```

Use a throwaway git repo with a policy from `delegate.py init`. AGENTS.md → Testing lists what to
re-check. To try the plugin from your clone in Claude Code, start a session with
`claude --plugin-dir <clone>/opencode-delegate`.

## Validators

Run before opening a pull request (CI runs the first three):

```bash
python3 -m py_compile opencode-delegate/skills/opencode/scripts/delegate.py
wc -m opencode-delegate/skills/opencode/SKILL.md          # must stay under 19,900
claude plugin validate .
```

If you have the [skill-creator-plus](https://github.com/yaniv-golan/skill-creator-plus) plugin,
also run, from that skill's directory:

```bash
python -m scripts.quick_validate <clone>/opencode-delegate/skills/opencode
python -m scripts.check_portability <clone>/opencode-delegate/skills/opencode --target claude-code
```

Version consistency across the five places is also checked by
[skill-packager](https://github.com/yaniv-golan/skill-packager-skill)'s `validate`
(`python3 -m skill_packager validate <clone>`, from its `scripts/` directory).

## Pull requests

Say what changed, how you smoke-tested it, and whether the version was bumped. Keep commit messages
free of AI session links and machine-local paths.

## Security

Please report vulnerabilities privately; see [SECURITY.md](SECURITY.md).
