#!/bin/sh
# Record (or run) the opencode-delegate protocol scenarios, one at a time, each with its own
# throwaway delegate state dir and a stopped server in between. Spends model tokens.
#   usage: ./record.sh <add-sub|parallel|timeout-recovery> [record|run]
# Needs CLAUDE_CODE_OAUTH_TOKEN in the environment (or pass --dotenv in COWORK_EXTRA): with a token,
# protocol uses a clean managed Claude config dir; without one it uses your real ~/.claude.
set -eu
name=${1:?scenario name}
mode=${2:-record}
here=$(cd "$(dirname "$0")" && pwd)
: "${CLAUDE_CODE_OAUTH_TOKEN:?set CLAUDE_CODE_OAUTH_TOKEN so protocol gets an isolated config dir}"
# Not under /var/folders (OpenCode 1.19.3 hangs there). Never port 4096 (the real server).
export OPENCODE_DELEGATE_HOME="/private/tmp/ocd-harness/$name"
export OPENCODE_DELEGATE_PORT=4098
rm -rf "$OPENCODE_DELEGATE_HOME"; mkdir -p "$OPENCODE_DELEGATE_HOME"
script="$here/../../opencode-delegate/skills/opencode/scripts/delegate.py"
trap 'python3 "$script" server stop >/dev/null 2>&1 || true' EXIT
case "$mode" in
  record) cowork-harness record "$here/scenarios/$name.yaml" --out "$here/cassettes/$name.cassette.json" \
            --max-budget-usd 15 --allow-host-inventory-fixture ${COWORK_EXTRA:-} ;;
  run)    cowork-harness run "$here/scenarios/$name.yaml" --keep ${COWORK_EXTRA:-} ;;
esac
