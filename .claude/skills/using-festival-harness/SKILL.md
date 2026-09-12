---
name: using-festival-harness
description: Use when starting any task in the FestivalApp repository - maps the task to the rules and workflow that apply to it
---

# Using the FestivalApp harness

You are in FestivalApp: a tablet POS for festival bar staff, plus an analytics app for
organisers, over a FastAPI backend and MongoDB. **The repository is public.**

Read [`CLAUDE.md`](../../../CLAUDE.md) for the map. This skill is the dispatch table.

## Always in force

| Rule | One-line version |
|---|---|
| [`public-repo-secrets`](../../rules/public-repo-secrets.md) | No secret ever lands in a commit. The repo is public. |
| [`base-branch`](../../rules/base-branch.md) | Branch from `origin/main`, land through a PR. Never commit to `main`. |
| [`no-work-in-scratch`](../../rules/no-work-in-scratch.md) | Work goes in the repo. The scratchpad is for logs. |
| [`no-guessing-on-code-claims`](../../rules/no-guessing-on-code-claims.md) | Grep before you claim. |
| [`writing-for-humans`](../../rules/writing-for-humans.md) | No em-dashes or marketing words in PRs, commits, README. |

## Dispatch by task

| You are about to... | Read first | Then |
|---|---|---|
| Build a feature or change behaviour | [`sales-data-invariants`](../../rules/sales-data-invariants.md) | `superpowers:brainstorming`, then `superpowers:writing-plans` |
| Execute a written plan | [`no-failing-tests`](../../rules/no-failing-tests.md) | `superpowers:subagent-driven-development` |
| Fix a bug | [`minimal-fixes`](../../rules/minimal-fixes.md) | `superpowers:systematic-debugging` |
| Touch orders, sync, voiding, or timestamps | [`sales-data-invariants`](../../rules/sales-data-invariants.md) | Change the test first, deliberately |
| Write or change a Mongo query | [`mongodb-queries`](../../rules/mongodb-queries.md) | Add the index in the same PR |
| Add or change a dependency | [`python-uv`](../../rules/python-uv.md) | `uv add`, commit `uv.lock` |
| Touch config, env vars, or deployment | [`public-repo-secrets`](../../rules/public-repo-secrets.md) | Values go to Render, names to `.env.example` |
| Build UI | — | `frontend-design` skill; touch targets at least 64px on the POS |
| Build a chart | — | `dataviz` skill, before the first line of chart code |
| Claim something is done | [`no-failing-tests`](../../rules/no-failing-tests.md) | `superpowers:verification-before-completion` |
| Open a PR | [`writing-for-humans`](../../rules/writing-for-humans.md) | `superpowers:requesting-code-review` |

## Running things

```bash
make help          # every target
make check         # what CI runs: lint, format check, tests
make test          # backend tests against a real local MongoDB
make dev           # backend with reload
```

First `make test` downloads MongoDB into `.tools/`. No Docker or sudo needed.

## Instruction priority

A direct instruction from the user beats `CLAUDE.md`, which beats these rules, which beat
your defaults. When a rule seems wrong for the situation, say so rather than silently
skipping it.
