# Minimal fixes — understand before you change

**Hard rule.** Before writing code to fix a problem, reproduce it and understand exactly
where the behaviour goes wrong. Then make the smallest intervention that fixes it.

## Why

The expensive failure mode is the opposite: leap to code, ship a multi-part fix, discover
a side effect, patch the side effect, discover another. Each round ends with a more
fragile pile of guards sitting on top of a misunderstood problem.

## Sequence

1. **Reproduce.** Get the actual failing output. Real numbers, not a paraphrase.
2. **Locate.** Name the file and line where the wrong decision is made. If you cannot, you
   do not understand the problem yet.
3. **Consider the blast radius.** What feeds this line, and what consumes its output?
4. **Design minimal.** A single condition beats a new branch. A new branch beats a new
   function. A new function beats a new module. Stop at the first level that works.
5. **Verify.** The failing case, then its neighbours, then the full suite.
6. **If the small change regresses something, do not patch the regression.** Revert and go
   back to step 2. Your understanding was wrong, not your fix size.

## Red flags

| Thought | Reality |
|---|---|
| "I will add a fallback in case my fix does not work" | You do not understand the problem. Back to step 2. |
| "I will wrap this in try/except to be safe" | Safety nets hide bugs. |
| "Option A, and if it regresses, fall through to B" | That is two code paths to maintain, both running. |
| "Let me also fix Y while I am here" | Y gets its own PR. |
| "A new service module for this one case" | Try the smallest change inside the existing structure first. |

The bar for a new file or class: you tried the minimal change, it did not fit, and you can
say why in one sentence.
