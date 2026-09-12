# Festival Sales App — Design

**Date:** 2026-09-12
**Status:** Approved for planning
**Repository:** https://github.com/GillesVandewiele/FestivalApp (public)

## 1. Purpose

Bar staff at a festival register drink orders in seconds on a tablet. Every sale is
kept, so the organisation can decide from real numbers — rather than memory — what to
buy for the next edition, how much of it, and where to put it.

Two audiences, two apps:

- **POS app** — bar staff. Speed is the only feature that matters.
- **Admin app** — organisers. Live monitoring during the festival, deep analysis after.

Source: `scope.txt`.

## 2. Scale and constraints

| Dimension | Value |
|---|---|
| Bars (verkooppunten) | 1–3 |
| Drinks sold per edition | < 10,000 |
| Concurrent tablets | ~3–6 |
| Orders per edition | ~3,000–5,000 (≈2 MB) |
| Peak write rate | < 1/s |
| Budget | €0 — free tiers only |
| Repository | **Public** on GitHub |
| Deadline | None; next year's festival |

At this volume neither storage nor throughput is a binding constraint. The design
optimises for **correctness, staff speed, and analytical depth**, not for scale.

## 3. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Two separate Vue apps, one backend | Tablets never load charting code; the organiser view is unreachable from a bar tablet |
| D2 | Immutable order event log, no pre-aggregation | One source of truth; counters can't drift; unanticipated questions stay answerable |
| D3 | Statistics computed on demand via aggregation | Instant at 5k documents; pre-aggregation would be premature |
| D4 | Dashboard polls every 15s (no WebSocket) | A sleeping free-tier backend handles persistent connections worst; polling gains the same result |
| D5 | Client-generated order IDs (UUIDv4) | Makes offline sync idempotent — retries can never duplicate a sale |
| D6 | Full offline-first PWA | Bars must sell through a total network outage, including after a tablet reboot |
| D7 | Coupons only; no cash, card or change | Confirmed with organiser: staff collects physical bonnetjes |
| D8 | No confirmation dialog; commit + undo instead | Mistakes are rare; a prompt on every order taxes the common case to guard the rare one |
| D9 | Soft-delete voids (`status: "voided"`) | Preserves the audit trail; void rate is itself a signal |
| D10 | Selling price snapshotted on the order; cost price is not | Price is a transaction fact; cost is an accounting attribute learned later from invoices |
| D11 | Stable `slug` per product across editions | Year-over-year comparison survives renames and re-pricing |
| D12 | Device enrolment tokens for tablets | Public repo means a public API surface; tokens are revocable per device |

### Rejected

- **Pre-aggregated counters** — optimises an already-instant query while adding drift bugs and complicating voids. Right at 50× this volume.
- **WebSocket live updates** — see D4. Cheap to add later if 15s ever feels slow.
- **Single app with role-based routing** — organiser explicitly wants two apps.
- **Vercel Hobby hosting** — its terms prohibit commercial use.
- **Fly.io / Koyeb** — both closed their free tiers to new users during 2026.

## 4. Architecture

```
┌─ apps/pos    (Vue 3 PWA)  ──┐        ┌──────────────┐      ┌─────────────┐
│  bar tablets, offline-first │───────▶│  FastAPI     │─────▶│ MongoDB     │
└─────────────────────────────┘        │  (Render)    │      │ Atlas M0    │
┌─ apps/admin  (Vue 3 SPA)  ──┐        │              │      │             │
│  organiser: stats + config  │───────▶└──────────────┘      └─────────────┘
└─────────────────────────────┘
   both on Cloudflare Pages
```

```
FestivalApp/
  backend/           FastAPI + Motor, Pydantic v2, pytest
  apps/pos/          bar staff PWA        (Vue 3, Vite, Pinia, vite-plugin-pwa, Dexie)
  apps/admin/        organiser app        (Vue 3, Vite, Pinia, ECharts)
  packages/shared/   TS types + API client generated from the OpenAPI schema
  docs/superpowers/specs/
```

### Hosting

| Component | Provider | Free-tier reality |
|---|---|---|
| Frontends | Cloudflare Pages | Never sleeps, commercial use permitted, global CDN |
| Backend | Render web service | 750 instance-h/month; **sleeps after 15 min idle, ~1 min cold start** |
| Database | MongoDB Atlas M0 | 512 MB, ~100 ops/s, one free cluster per project |

The cold start is made invisible rather than merely tolerated: the frontends are static
and always up, and the POS app is offline-first, so a tablet loads and sells while the
backend is still waking. A free cron ping keeps the backend warm on festival days only
— running it permanently would consume ~730 of the 750 monthly hours.

## 5. Data model

Eight collections. All festival data is edition-scoped, so history accumulates rather
than being overwritten; only `users` is global.

```js
// editions
{ _id, name: "Festival 2026", year: 2026,
  starts_at, ends_at, timezone: "Europe/Brussels",
  coupon_value_eur: 2.50, is_active: true }

// bars (verkooppunten)
{ _id, edition_id, name: "Hoofdpodium", sort_order, active }

// products
{ _id, edition_id,
  slug: "jupiler",              // STABLE across editions — the year-over-year join key
  name: "Jupiler", category: "bier",
  price_coupons: 1,             // selling price
  cost_price_eur: 0.62,         // purchase cost, may be entered after the festival
  purchase_unit: { name: "bak", size: 24 },
  purchased_qty: null, leftover_qty: null,   // optional, for waste analysis
  available_at: [bar_id, ...],  // per-bar assortment
  sort_order, active }

// staff
{ _id, edition_id, name: "Lotte", active }

// orders — immutable event log
{ _id: "9f3c…",                 // UUIDv4 minted on the tablet = idempotency key
  edition_id, bar_id, staff_id, device_id,
  items: [{ product_id, slug, name, qty, unit_price_coupons }],  // snapshotted
  total_coupons,
  created_at,                   // when the sale happened (skew-corrected, UTC)
  received_at,                  // when the server accepted it
  status: "confirmed" | "voided",
  void: { at,
          by: { type: "staff" | "user", id },   // staff undo vs organiser correction
          reason }              // null for a staff undo; required for an admin void
}                               // `void` present only when status is "voided"

// stockouts
{ _id, edition_id, bar_id, product_id, slug,
  out_at, back_at }             // back_at null while still sold out

// users — organiser logins
{ _id, email, password_hash, role: "organizer" | "admin", created_at }

// devices — enrolled tablets
{ _id, edition_id, bar_id, label: "Tablet bar 1",
  token_hash,                   // HMAC-SHA256(token, server pepper)
  enrolled_at, last_seen_at, revoked_at }
```

### Indexes

```
orders:    { edition_id: 1, created_at: 1 }
           { edition_id: 1, status: 1, created_at: 1 }
           { edition_id: 1, bar_id: 1, created_at: 1 }
           { edition_id: 1, staff_id: 1 }
products:  { edition_id: 1, slug: 1 }  unique
           { slug: 1 }                          // year-over-year lookups
devices:   { token_hash: 1 }  unique
users:     { email: 1 }       unique
stockouts: { edition_id: 1, product_id: 1, out_at: 1 }
```

### Why prices are snapshotted but costs are not

A sale's coupon price is a fact about that transaction: correcting a mispriced cocktail
at 18:00 must not rewrite what was charged at 17:00. Cost price is an accounting
attribute that is often only known *after* the festival, when supplier invoices arrive.
Storing cost on the product and joining at report time means entering invoices in
December makes every historical margin report correct at once.

### Clock skew

Hourly breakdown is a headline statistic, and a tablet with a wrong clock or timezone
would silently corrupt it. On startup and after each successful sync the tablet calls
`GET /api/v1/time`, stores `offset = server_time - device_time`, and stamps
`created_at = device_now + offset`. A tablet offline all evening still reports the
correct hour. The server additionally records `received_at` from its own clock, so any
residual disagreement is detectable after the fact.

## 6. POS app (`apps/pos`)

```
┌────────────────────────────────────────────┐
│  Bar Hoofdpodium          Lotte  ⟳ synced  │
├──────────────┬──────────────┬──────────────┤
│    JUPILER   │  WITTE WIJN  │     CAVA     │
│      1 🎫    │     2 🎫     │     3 🎫     │
│      ×3      │              │              │
├──────────────┼──────────────┼──────────────┤
│     COLA     │    WATER     │  GIN-TONIC   │
│     1 🎫     │     1 🎫     │     4 🎫     │
│              │     ×2       │              │
├──────────────┴──────────────┴──────────────┤
│  ↶ UNDO  │      5 BONNETJES        ✓       │
└────────────────────────────────────────────┘
```

**A five-drink round is six taps** — three on `JUPILER`, two on `WATER`, one on the
total bar. No dialogs, no menus, no second screen.

| Action | Gesture |
|---|---|
| Add a drink | Tap the product (repeat taps increment the count) |
| Remove before committing | Long-press the product to decrement |
| Commit the order | Tap the green total bar — clears instantly for the next customer |
| Undo the last order | Tap `↶ UNDO` — voids it, no dialog |
| Undo an older order | Long-press `↶ UNDO` → last 10 orders from this tablet |
| Mark a product sold out | Long-press the product header → `OP!`; button greys out |
| Mark it back in stock | Long-press the greyed-out product again |
| Change staff member | Tap the name in the header |

The undo list holds the **last 10 orders committed on this tablet**, with no time limit
— an order can be undone whether or not it has already synced (see §6 sync, rule 5). A
sold-out product's button is greyed and non-tappable, so a customer cannot be charged
for a drink that isn't there.

Rules:

- **No confirmation prompt anywhere.** The total bar *is* the confirmation, and it is a
  tap that is needed regardless to delimit one customer from the next.
- **The commit button debounces** (400 ms) and immediately becomes `UNDO`, so a
  double-tap cannot create two orders.
- **Staff selection is once per shift** — tap your name on arrival, stay logged in.
- Installed as a fullscreen PWA; Wake Lock keeps the screen alive; pull-to-refresh and
  overscroll are disabled; the sync indicator shows `12 orders queued` explicitly.
- Touch targets ≥ 64 px, high contrast, legible in daylight and in the dark.

### Offline sync

1. A committed order is written to IndexedDB and rendered as done immediately. The UI
   never waits on the network.
2. A background task drains the queue whenever connectivity allows, posting batches to
   `POST /api/v1/sync/orders`.
3. The server upserts by `_id`. Retries are therefore idempotent — a sale cannot be
   duplicated no matter how many times a flaky connection retries it.
4. **An order voided before it has ever synced is sent once, already marked
   `voided`** — one write, complete audit trail, no orphan record.
5. **Voiding an already-synced order needs no separate endpoint**: the tablet re-sends
   the same `_id` with `status: "voided"`, and the upsert applies it. The server
   enforces `status` as a **one-way transition** — `confirmed → voided` is accepted,
   `voided → confirmed` is rejected — so a stale tablet replaying an old queue can
   never resurrect a voided sale.
6. Catalog, staff and bar data are cached at enrolment and refreshed on each sync, so a
   rebooted tablet with no network still starts up and sells.

## 7. Admin app (`apps/admin`)

### Live (polls every 15 s)

Total consumptions and coupons; per drink; per bar; per staff member; sales-per-hour
bar chart building through the evening; currently sold-out products.

### Configure

Editions, bars, staff, and the drinks catalog — coupon price, cost price, category,
purchase unit, per-bar availability. Changes reach tablets on their next sync.

### Reports

| Report | Question it answers |
|---|---|
| Profit per product | Sold, coupons, revenue €, cost €, margin €, margin % |
| Margin–volume quadrant | Which products to promote, reprice, or drop |
| Pareto curve | Which handful of products carry 80% of volume |
| Hourly demand | When to staff up; whether the mix shifts late at night |
| Peak throughput per bar | How much stock and cooling each bar actually needs |
| Per-bar product mix | How to allocate stock across verkooppunten |
| Year-over-year | Per-product growth and the comparison table from the scope |
| Procurement plan | What to order for next year, in whole crates, with the total cost |
| Waste | Bought vs sold vs left over, and the euros tied up in leftovers |

`revenue_eur = total_coupons × edition.coupon_value_eur`
`cost_eur = units_sold × product.cost_price_eur`
`margin_eur = revenue_eur − cost_eur`

Every report is exportable to CSV.

#### Procurement plan

```
Product      Sold   Growth   Advised   Purchase unit   To order    Cost
Jupiler      8,420   +8%      9,550    bak van 24      398 bakken  €5,918
Cava           860   -18%       740    doos van 6      124 dozen   €1,041
Water        2,110   +24%     2,720    bak van 24      114 bakken    €592
                                                       TOTAL     €12,340
```

```
advised   = sold × (1 + growth) × (1 + safety)
to_order  = ceil(advised / purchase_unit.size)
```

- `growth` — observed per-product year-over-year growth when two or more editions
  exist; otherwise an expected-attendance change entered by the organiser (default 0%).
- `safety` — a configurable buffer, **default 10%, automatically raised to 25% for any
  product that recorded a stockout**. Both figures are editable per report run.
- **Every row expands to show this arithmetic**, and any row can be overridden by hand.
  A forecast that cannot be audited will not be trusted a year later.

#### Stockouts and censored demand

If Jupiler ran dry at 23:00, the 8,420 sold measures supply, not demand — and
forecasting next year from it under-buys again, compounding each edition. Products with
a recorded stockout are flagged in the procurement plan, receive a raised safety buffer,
and display the time at which demand was cut off.

## 8. API

Versioned under `/api/v1`. FastAPI generates the OpenAPI schema; `packages/shared`
generates its TypeScript client from it, so frontend and backend types cannot drift.

**Device-authenticated (POS)**

```
GET  /time                      server clock, for skew correction
GET  /bootstrap                 edition, bar, products, staff — everything cached
POST /sync/orders               batch idempotent upsert; returns accepted IDs
POST /sync/stockouts            batch upsert of sold-out markers
```

**Session-authenticated (admin)**

```
POST   /auth/login  /auth/logout  /auth/me
CRUD   /admin/editions | bars | products | staff
POST   /admin/devices/enroll     issue a short-lived enrolment code
POST   /admin/devices/{id}/revoke
GET    /stats/overview | by-product | by-bar | by-staff | by-hour
GET    /stats/compare?editions=2025,2026
GET    /stats/procurement?edition=…&growth=…&safety=…
POST   /orders/{id}/void         organiser correction (requires a reason);
                                 staff undo goes through /sync/orders instead
GET    /export/{report}.csv
```

## 9. Security

The repository is public, so configuration must be genuinely externalised rather than
merely undocumented.

| Concern | Measure |
|---|---|
| Secrets in git | `.env` gitignored; `.env.example` holds placeholders only; `gitleaks` pre-commit hook. GitHub secret scanning, **push protection**, Dependabot alerts and Dependabot security updates are enabled on the repository (done 2026-09-12). Generic (non-provider) secret patterns could not be enabled via the API — `gitleaks` covers that gap locally |
| Database credentials | Dedicated Atlas user, `readWrite` on one database only, long generated password |
| Atlas network access | Render's free tier has no fixed egress IP, so `0.0.0.0/0` is required. Stated plainly; credential scope above is the compensating control |
| Tablet authentication | Long random device token, stored server-side as HMAC-SHA256 with a server pepper. A database dump yields no working tokens. Revocable per device |
| Enrolment | Short-lived, single-use code issued from the admin app |
| Organiser passwords | argon2id |
| Sessions | JWT in `HttpOnly; Secure; SameSite=Strict` cookies, short expiry |
| CORS | Explicit two-domain allowlist, never `*` |
| Rate limiting | On `/auth/*` and all `/sync/*` endpoints |
| Transport | HTTPS everywhere; HSTS and security headers via Cloudflare Pages `_headers` |
| Dependencies | Dependabot; CI runs `pip-audit` and `npm audit` |
| Personal data | Staff first names or nicknames only — no customer data of any kind |

No secret ever reaches the browser: frontend bundles are public regardless of the
repository's visibility, so all credentials live in Render's environment configuration.

## 10. Error handling

| Failure | Behaviour |
|---|---|
| Network lost mid-shift | Orders queue locally; indicator shows the queue depth; selling continues unaffected |
| Backend cold-starting | Sync retries with exponential backoff; no user-visible error |
| Tablet reboots offline | App loads from cache with catalog intact; queued orders survive in IndexedDB |
| Duplicate submit | Server upserts by client-supplied `_id`; no duplicate sale is possible |
| Tablet clock wrong | Corrected via the server-time offset; `received_at` preserves the discrepancy |
| Sync payload rejected | The offending order is quarantined locally and surfaced in the admin app rather than silently dropped |
| Atlas unreachable | Backend returns 503; tablets keep queueing; nothing is lost |
| Staff forgot to switch user | Admin can reassign an order's staff member after the fact |

## 11. Testing

- **Backend, pytest** — golden tests for every aggregation against a seeded fixture
  dataset. This is where a silently wrong number does the most damage, because a wrong
  total looks entirely plausible. Also covers auth, idempotent upsert, and void
  semantics.
- **Frontend, Vitest** — the offline queue's hard cases: retry after failure,
  void-before-sync, clock skew, duplicate submit, catalog refresh while orders queue.
- **End-to-end, Playwright** — the six-tap sale, undo, and an offline→online sync cycle.
- **CI** — GitHub Actions runs lint, types, unit tests, `gitleaks`, and dependency
  audits on every push.

Development follows TDD: a failing test precedes each behaviour.

## 12. Delivery order

1. **Foundation** — repo scaffold, CI, Atlas + Render + Pages deploys, health check.
2. **Data and API** — collections, indexes, models, admin CRUD, auth, device enrolment.
3. **POS app** — order grid, commit/undo, staff selection, offline queue, sync, PWA.
   *Reviewed on a real tablet before proceeding.*
4. **Live dashboard** — aggregations plus the live view.
5. **Reports** — profit, quadrant, Pareto, hourly, per-bar, CSV export.
6. **Procurement and stockouts** — stockout marking, waste, the procurement engine.
7. **Year-over-year** — comparison views, exercised with two seeded editions.

Steps 1–3 constitute a system that can already run a festival; 4–7 add the analytical
value. Because there is no deadline pressure, each step ships tested rather than
deferred to a hardening phase.

## 13. Open items

- **Coupon value in euros** — needed for revenue and margin. Configurable per edition;
  organiser supplies the 2026 figure before reports are used.
- **Custom domain** — the design assumes two Cloudflare Pages subdomains. Defaults to
  `*.pages.dev` if no domain is provided; nothing depends on the choice.
