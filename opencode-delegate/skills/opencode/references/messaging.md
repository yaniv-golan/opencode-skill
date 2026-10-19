# Messaging: peers and recovery

**Peers:** `pair --repo <repo> --task A --with B` lets two tasks message each other. Pair only tasks whose work really interlocks. A peer message never changes a task's brief.

Orchestrate from the main conversation, not from a subagent: a subagent's hooks don't receive messages, and its prompt cache expires after 5 minutes. After `/clear` your session id changes, so messages to the old session sit unread. Read them with `inbox --session <old id>`.

**What a task can send.** A run gives OpenCode three tools: `message_orchestrator` (a one-way
note), `ask_orchestrator` (blocks the task until you answer, for up to 20 minutes) and
`send_message` (to a paired task). Each run allows 5 messages of at most 4 KB each. They reach you
from `wait` or `run --wait`, or through the plugin's hooks at your next tool step. If you lose
track after compaction, `list` shows every task's state and last run.
