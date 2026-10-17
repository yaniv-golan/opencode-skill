# Messaging: peers and recovery

**Peers:** `pair --repo <repo> --task A --with B` lets two tasks message each other. Pair only tasks whose work really interlocks. A peer message never changes a task's brief.

Orchestrate from the main conversation, not from a subagent: a subagent's hooks don't receive messages, and its prompt cache expires after 5 minutes. After `/clear` your session id changes, so messages to the old session sit unread. Read them with `inbox --session <old id>`.
