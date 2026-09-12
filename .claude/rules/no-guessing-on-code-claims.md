# No guessing on code claims

**Hard rule.** Before stating anything factual about code structure or behaviour, read or
grep the source. "Likely", "probably", "I think", "should be", "appears to" in a claim
about code means you are speculating where you should be checking.

## What counts

If your sentence names a function, a field, a route, a collection, or asserts a behaviour,
it is a code claim. Verify it.

- "This endpoint requires a device token."
- "Nothing reads this field."
- "The aggregation excludes voided orders."
- "This index covers that query."

## Why

Speculation is the failure mode that wastes the most user time: they either redo the
analysis to catch the error, or accept it and ship a wrong design. Greping a symbol takes
ten seconds. Cleaning up after a wrong claim costs a review cycle.

## How to apply

- Ask yourself: did I read this, or am I remembering it? If you can name the file and
  line, you read it.
- If you cannot, open the file or grep the symbol, then write the sentence.
- Hedging is fine for judgment calls ("I think A beats B"). This rule is about factual
  claims, not opinions.

## Recovery

If the user pushes back on a claim, do not defend it and do not partially patch it. Verify
every claim in the set and re-issue it. The fix is the verification, not the apology.
