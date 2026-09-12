# Base branch

The base branch for FestivalApp is **`main`**.

- All PRs target `main`.
- New branches are created from `origin/main`.
- **Never commit, push, or merge directly to `main`.** Every change lands through a PR,
  including design docs, plan files, harness edits, and one-line typos.
- Never force-push to `main`.

## Why a PR for everything, on a solo project

- CI runs on pull requests. Committing straight to `main` skips the tests, the gitleaks
  scan, and the dependency audit.
- A bad PR reverts in one click. A bad commit on `main` needs a follow-up commit.
- The repository is public. The PR trail is the only record of why a change was made.

## Usage

This file is the single source of truth for the branch name. Extract it rather than
hardcoding:

```bash
BASE=$(grep -oP '\*\*`\K[^`]+' .claude/rules/base-branch.md | head -1)
git checkout "origin/$BASE" -b <slug>
```

If extraction fails, ask rather than guess.

## Recovery if you slipped

Tell the user immediately. Do not paper over it. Then either revert on `main` and re-land
through a PR, or, if the change is genuinely trivial and the user accepts, leave it and
record the exception. Never `git reset --hard` plus force-push to tidy it away: that
destroys the audit trail and is itself a destructive operation on a protected branch.
