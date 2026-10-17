#!/bin/sh
# Fast path for the opencode-delegate message hooks. python3 startup alone costs ~235 ms and
# this runs on every tool call, so only start Python when this session actually has a mailbox.
# A mailbox file exists only while at least one message is pending (msg_ack deletes it once
# everything is acknowledged), so its absence is the cheap "nothing to deliver" answer.
input=$(cat)

sid=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
case "$sid" in
  ''|*[!A-Za-z0-9-]*) exit 0 ;;
esac

home="${OPENCODE_DELEGATE_HOME:-$HOME/.local/state/opencode-delegate}"
[ -f "$home/msg/sessions/$sid.jsonl" ] || exit 0

printf '%s' "$input" | exec python3 "$(dirname "$0")/../skills/opencode/scripts/delegate.py" hook
