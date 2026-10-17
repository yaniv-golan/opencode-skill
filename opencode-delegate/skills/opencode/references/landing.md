# Landing a task, in detail

Read before `land`, `apply`, a merge, or `remove`.

With the user's go-ahead, land it in one of three ways:

- **`land`** = `apply` + `remove --delete-branch` in one step. `--commit -m "<msg>"` also commits
  exactly the task's files in the user's checkout, with their own identity and hooks. It refuses
  if any of those files has the user's own uncommitted changes, and leaves other staged work
  alone. Commit only when the user asked for a commit and approved the message.

- **`apply` (default; required for `--from-working-tree` tasks)** puts the task's changes into the
  user's working tree as unstaged edits, on top of whatever they have there now. Dry-run first:

      delegate.py apply --repo <repo> --task <slug> --check
      delegate.py apply --repo <repo> --task <slug>

  `apply` first commits any edits still uncommitted in the worktree (as `manual edits before
  apply`). Exit codes of `apply`: 0 applied (or `--check` clean), 2 nothing to apply or already
  applied, 6 conflicts. Exit 6 means nothing was changed: re-run the task with `--from-working-tree` on a
  new `--task`, or ask before `--3way` (it touches the index and can leave conflict markers). The
  user then reviews and commits as they normally would.
- **Merge or cherry-pick `opencode/<slug>`**, only for tasks based on a commit, following the repo's
  rules. Never merge a snapshot-based branch: its base commit contains the user's uncommitted work.

Clean up afterwards:

    delegate.py remove --repo <repo> --task <slug> [--delete-branch]

`remove` refuses while the worktree has uncommitted changes (`--force` discards them — only on the
user's say-so). `remove --delete-branch` also refuses, and removes nothing, while the task's attempts
were neither applied nor merged. Task branches and refs are local working state: don't push them, and never use
`git push --mirror` in a repo with snapshot tasks (it pushes every ref, including
`refs/opencode-delegate/*`). `remove --delete-branch` deletes the branch or private ref too.

