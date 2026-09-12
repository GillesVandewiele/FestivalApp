# Sales data invariants

The product exists to leave behind a trustworthy dataset. These invariants are what make
it trustworthy. Breaking one does not throw an error; it quietly produces numbers that
look plausible and are wrong, and nobody finds out until they order next year's stock.

Every one of these has a test. If you change behaviour here, the test must change first,
deliberately, with the reason in the PR.

## 1. The tablet owns the order ID

Order `_id` is a UUIDv4 generated on the tablet before the order is ever sent. The server
upserts on it.

**Why:** it makes retrying free. A tablet on a flaky link can send the same order ten
times and produce one document. Without it, offline sync needs coordination the network
cannot provide.

## 2. Status is a one-way ratchet

`confirmed` to `voided` is accepted. `voided` to `confirmed` is rejected.

**Why:** a tablet that has been offline can replay a stale queue containing the original
confirmed copy of an order that was later voided. Without the ratchet, the replay
resurrects a cancelled sale.

## 3. The server never trusts the client's totals or identity

`total_coupons` is recomputed from the line items. `device_id` comes from the
authenticated token, not the payload. `OrderIn` does not even declare these fields.

## 4. Selling price is snapshotted, cost price is not

Each order line stores the `name` and `unit_price_coupons` it was sold at. Correcting a
mispriced product must never rewrite what was charged earlier.

Cost price lives on the product and is joined at report time, because invoices arrive
after the festival. Entering them in December must make every historical margin report
correct at once.

## 5. Product slug is the year-over-year key

`slug` is stable across editions and unique within one. Comparison across years groups on
it, so renaming a product or changing its price must not break the comparison.

## 6. Voids are soft

A void sets `status` and a `void` block. Nothing is ever deleted. Void rate per staff
member is itself a signal worth reading.

## 7. Timestamps

`created_at` is when the sale happened, corrected for tablet clock skew against
`GET /api/v1/time`. `received_at` is server-side and set once, on insert, never on a
retry. Both are timezone-aware UTC.

**Why it matters:** sales-per-hour is a headline statistic. A tablet with a wrong
timezone would silently shift a whole evening's data into the wrong buckets.

## 8. Stockouts mean demand was censored

A product that ran out did not sell what people wanted; it sold what was in stock.
Forecasts that ignore this under-buy the same product every year, compounding. Anything
that computes purchasing advice must account for recorded stockouts, not just units sold.

## 8b. A stockout estimate refuses to guess

`stockout_impact` projects a product's share of sales before it ran out onto everything
sold while it was gone. It returns `estimated_lost: null` when there is too little to go
on: fewer than 10 sold beforehand, or less than 30 minutes of trading. Its window is
bounded by the edition's own dates, not by the first and last order, so one sale with a
wrong timestamp cannot stretch it by weeks.

**Why:** the estimate feeds a purchase order. A fabricated number there is worse than an
honest gap, because nobody can tell it apart from a measured one.

## 9. Staff drinks are recorded but never counted as revenue

`Order.kind` is `"sale"` or `"staff"`. **Every aggregation filters on it.** A staff drink
is stored with its items and its coupon value, so the report can say what those drinks
would have been worth, but it is never charged and never appears in a revenue, margin, or
purchasing figure.

**Why:** a pipeline that forgets the filter reports free drinks as income at full coupon
price. That is worse than not tracking staff drinks at all, because the number looks
right. It also inflates next year's purchasing advice with demand that was never paid for.

The POS toggle resets after every commit for the same reason: an accidentally sticky
`personeel` mode would book a paying customer's round as free, and nothing downstream
would flag it.
