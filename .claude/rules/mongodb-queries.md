# MongoDB queries and indexes

Indexes are declared in one place, `backend/app/db.py::ensure_indexes`, which runs on
startup and is idempotent. There is no migration tool and at this data volume there does
not need to be.

## When you add or change a query

Check whether its filter, sort, and grouping fields are covered by an existing index. If
not, add one to `ensure_indexes` in the same PR as the query, and add a test asserting the
index exists (see `backend/tests/test_db.py`).

## Do not add an index "just in case"

Index count trades write latency for read speed. Before adding one, check for prefix
overlap with what is already there: `{edition_id, status, created_at}` already covers
`{edition_id, status}` and `{edition_id}`.

## Verify the plan for anything non-trivial

```python
await db.orders.find(query).explain("executionStats")
```

Confirm the winning stage is not `COLLSCAN` and that `totalDocsExamined` is within an
order of magnitude of `totalDocsReturned`. Aggregation pipelines: check that `$match` runs
before `$group`, and that the `$match` is index-backed.

## Scale context

An edition is roughly 5,000 order documents, about 2 MB. Atlas M0 allows 512 MB and
around 100 operations per second. Nothing here is performance-critical, so **prefer the
clear query over the clever one**. Reach for an index because a query needs it, not
because indexing feels thorough.

## Aggregations must exclude voided orders

Every statistic filters `status: "confirmed"` unless it is deliberately reporting on
voids. A pipeline that forgets this silently inflates every number it produces.
