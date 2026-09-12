# Demo feedback (Justine) — design note

A shorter document than the other plans on purpose. These are six well-specified
requests from a stakeholder demo, not an open design question, so what follows is the
decisions rather than a bite-sized walkthrough. Four of them change stored data or an
invariant, which is why they are written down at all.

**Spec:** `docs/superpowers/specs/2026-09-12-festival-sales-app-design.md`

## 1. Category rows in the POS grid, and categories managed in the app

Today `product.category` is a free string and the POS maps five hardcoded names to five
hardcoded colours. Justine wants categories on their own rows and wants to add and remove
them without a developer.

**Decision: a `categories` collection, edition-scoped.**

```js
{ _id, edition_id, slug, name, colour, sort_order }
```

`product.category` stays a **slug string**, not a foreign key. Two reasons: existing
documents keep working untouched, and year-over-year comparison already joins on slugs, so
a renamed category cannot orphan history.

- Colour moves out of the POS stylesheet into the database, because a user-created
  category has no stylesheet entry. The admin offers a fixed set of validated swatches
  rather than a free colour picker: a free picker produces unreadable buttons.
- Deleting a category that products still use returns **409**, naming the products. Silent
  reassignment would move drinks into a category nobody chose.
- The POS groups the grid by category in `sort_order`, one labelled row each.

## 2. Staff drinks

Staff take drinks without paying, and the organisation still wants the count. This is the
one change that touches an invariant, because every existing statistic would otherwise
count free drinks as revenue.

**Decision: `Order.kind: "sale" | "staff"`, default `"sale"`.**

- **Every aggregation filters `kind: "sale"`.** A pipeline that forgets this reports staff
  drinks as revenue at full coupon price, which is worse than not tracking them at all.
  This joins the list in `.claude/rules/sales-data-invariants.md`.
- A staff order still records its items and coupon value, so the report can say what the
  drinks would have been worth. It is stored, not charged.
- POS placement is deliberately quiet: a small toggle in the header, not a button next to
  the drinks. It flips the commit bar to a distinct colour reading `personeel`, and
  **resets to normal after every commit** so it cannot be left on by accident.
- New `GET /api/v1/stats/staff-consumption`: per staff member and per product, with the
  coupon value those drinks represent.

## 3. Shorter device codes

`secrets.token_urlsafe(32)` is 43 mixed-case characters with symbols. Nobody should type
that.

**Decision: 12 characters of Crockford base32, shown as `XXXX-XXXX-XXXX`.**

- The alphabet excludes `I`, `L`, `O` and `U`, so there is no ambiguity to mistype and
  nothing accidentally rude.
- 12 characters over a 32-symbol alphabet is **60 bits**. Short enough to read aloud,
  large enough that guessing is not a threat.
- Input is normalised before hashing: uppercased, dashes and spaces stripped, and `I`/`L`
  folded to `1` and `O` to `0`. Someone reading a code aloud cannot get it wrong.
- **60 bits is only safe with a guess limit**, so failed device authentications are
  throttled per IP: 20 failures in 5 minutes and that address is refused. At 4 guesses a
  minute, searching the space takes on the order of 10^17 minutes.
- Existing long tokens keep working. The hash does not care how long its input was.

## 4. Hourly chart: stacked by drink, with a metric toggle

- `by_hour` gains `revenue_eur` and `margin_eur` alongside `qty` and `coupons`, so the
  toggle switches between consumpties, omzet and marge without a second round trip.
- A new `by_hour_by_product` returns per-hour, per-drink quantities for the stack.
- The validated palette has **eight** slots on the adjacent pairlist used by stacked bars.
  With a dozen drinks that is seven plus **Overig**, never a ninth generated hue.
- Margin per hour needs the cost price, which is often missing. Hours where no product has
  a cost report `null`, and the toggle says so rather than drawing a zero line.

## Not doing

- **A free colour picker for categories.** Validated swatches only.
- **Reassigning products when a category is deleted.** Refuse and name them instead.
- **Making staff orders invisible.** They are stored and reported, just never counted as
  revenue.
