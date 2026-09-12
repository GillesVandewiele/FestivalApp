# Documentation index

## Design

- [Festival sales app design](superpowers/specs/2026-09-12-festival-sales-app-design.md)
  — data model, API, security, and the reasoning behind each decision. Authoritative.

## Plans

One plan per subsystem. Each leaves the repository with working software.

| # | Plan | Delivers |
|---|---|---|
| 1 | [Foundation and backend](superpowers/plans/2026-09-12-foundation-and-backend.md) | Data model, auth, device enrolment, sync API, CI, deploy |
| 2 | POS app (not yet written) | The tablet PWA, offline queue, sync |
| 3 | Admin shell and live view (not yet written) | Login, catalog configuration, live dashboard |
| 4 | Reports (not yet written) | Profit, quadrant, Pareto, procurement, year-over-year |

## Harness

- [`../CLAUDE.md`](../CLAUDE.md) — repository map, invariants, tooling.
- [`../.claude/rules/`](../.claude/rules/) — the rules that always apply.
- [`../.claude/skills/using-festival-harness/SKILL.md`](../.claude/skills/using-festival-harness/SKILL.md)
  — dispatch table from task to rule and workflow.

## Operations

- `DEPLOYMENT.md` — written in plan 1, task 13.
