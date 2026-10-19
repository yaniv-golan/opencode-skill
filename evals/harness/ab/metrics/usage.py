#!/usr/bin/env python3
"""Print one number from a run's events.jsonl: cost_usd, api_calls or duration_s.

cost_usd and duration_s come from the agent's final `result` event; api_calls counts distinct
assistant message ids (main loop and sub-agents). Lines with an `_emu` key are the harness's own."""
import json, sys

events, field = sys.argv[1], sys.argv[2]
result, ids = None, set()
with open(events) as f:
    for line in f:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict) or "_emu" in d:
            continue
        if d.get("type") == "result":
            result = d
        elif d.get("type") == "assistant":
            mid = (d.get("message") or {}).get("id")
            if mid:
                ids.add(mid)
if field == "api_calls":
    print(len(ids))
elif result is None:
    sys.exit("no result event")
elif field == "cost_usd":
    print(result.get("total_cost_usd", 0))
elif field == "duration_s":
    print(round(result.get("duration_ms", 0) / 1000, 1))
else:
    sys.exit(f"unknown field {field}")
