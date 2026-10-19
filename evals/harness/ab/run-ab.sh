#!/bin/sh
# Direct-vs-delegate A/B: cowork-harness eval over scenarios/, arm "direct" (a stub skill that does the
# work itself) vs arm "delegate" (opencode-delegate at a released tag). Spends model tokens.
#   usage: ./run-ab.sh <tag, e.g. v2.2.0> [extra eval args, e.g. --reps 1 or --dry-run]
# Needs CLAUDE_CODE_OAUTH_TOKEN, in the environment or in $AB_DOTENV (default
# ~/.cowork-harness/opencode-ab.env, outside the repo): without one, protocol runs on your real
# ~/.claude, whose installed plugins and instructions would contaminate both arms. Delegate state goes
# to a throwaway dir on port 4098, never the real 4096 server.
set -eu
tag=${1:?release tag}; shift
here=$(cd "$(dirname "$0")" && pwd)
dotenv=${AB_DOTENV:-$HOME/.cowork-harness/opencode-ab.env}
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
  grep -q '^CLAUDE_CODE_OAUTH_TOKEN=.' "$dotenv" 2>/dev/null ||
    { echo "no CLAUDE_CODE_OAUTH_TOKEN in the environment or in $dotenv" >&2; exit 2; }
  set -- --dotenv "$dotenv" "$@"
fi
export OPENCODE_DELEGATE_HOME="/private/tmp/ocd-ab"   # not under /var/folders (OpenCode 1.19.3 hangs there)
export OPENCODE_DELEGATE_PORT=4098
rm -rf "$OPENCODE_DELEGATE_HOME"; mkdir -p "$OPENCODE_DELEGATE_HOME"
script="$here/../../../opencode-delegate/skills/opencode/scripts/delegate.py"
trap 'python3 "$script" server stop >/dev/null 2>&1 || true' EXIT
cowork-harness eval "$here/scenarios" \
  --arm direct="$here/direct-plugin" --arm delegate="git:$tag:opencode-delegate" \
  --model claude-opus-5-5 "$@"
