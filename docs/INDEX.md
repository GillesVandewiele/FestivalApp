# Documentation index

## Design

- [Festival sales app design](superpowers/specs/2026-09-12-festival-sales-app-design.md)
  — data model, API, security, and the reasoning behind each decision. Authoritative.

## Plans

One plan per subsystem. Each leaves the repository with working software.

| # | Plan | Delivers |
|---|---|---|
| 1 | [Foundation and backend](superpowers/plans/2026-09-12-foundation-and-backend.md) | Data model, auth, device enrolment, sync API, CI, deploy. **Code complete, awaiting hosting setup.** |
| 2 | [POS app](superpowers/plans/2026-09-12-pos-app.md) | The tablet PWA, offline queue, sync |
| 3 | [Admin app](superpowers/plans/2026-09-12-admin-app.md) | Aggregations, config UI, live dashboard, reports, procurement |
| 4 | [Demo feedback](superpowers/plans/2026-09-12-demo-feedback.md) | Categories, staff drinks, typeable codes, hourly split |

## Harness

- [`../CLAUDE.md`](../CLAUDE.md) — repository map, invariants, tooling.
- [`../.claude/rules/`](../.claude/rules/) — the rules that always apply.
- [`../.claude/skills/using-festival-harness/SKILL.md`](../.claude/skills/using-festival-harness/SKILL.md)
  — dispatch table from task to rule and workflow.

## Operations

- [`DEPLOYMENT.md`](DEPLOYMENT.md) — Atlas, Render and Cloudflare Pages setup, environment
  variables, secret rotation, troubleshooting.
- [`TODO.md`](TODO.md) — everything only the organiser can do, before and after a festival.
