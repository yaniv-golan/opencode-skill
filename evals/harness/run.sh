#!/bin/sh
# Run one opencode-delegate protocol scenario live, with its own throwaway delegate state dir on the
# test port and its server stopped afterwards. Spends model tokens. No cassettes are recorded: the
# command-level checks read host paths that redaction would make unverifiable on replay.
#   usage: ./run.sh <add-sub|parallel|timeout-recovery>
# Needs CLAUDE_CODE_OAUTH_TOKEN in the environment: with a token, protocol uses a clean managed
# Claude config dir; without one it uses your real ~/.claude (and any installed copy of the plugin).
set -eu
name=${1:?scenario name}
here=$(cd "$(dirname "$0")" && pwd)
: "${CLAUDE_CODE_OAUTH_TOKEN:?set CLAUDE_CODE_OAUTH_TOKEN so protocol gets an isolated config dir}"
# Not under /var/folders (OpenCode 1.19.3 hangs there). Never port 4096 (the real server).
export OPENCODE_DELEGATE_HOME="/private/tmp/ocd-harness/$name"
export OPENCODE_DELEGATE_PORT=4098
rm -rf "$OPENCODE_DELEGATE_HOME"; mkdir -p "$OPENCODE_DELEGATE_HOME"
script="$here/../../opencode-delegate/skills/opencode/scripts/delegate.py"
trap 'python3 "$script" server stop >/dev/null 2>&1 || true' EXIT
cowork-harness run "$here/scenarios/$name.yaml" --keep ${COWORK_EXTRA:-}
