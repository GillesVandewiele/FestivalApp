# No failing tests

A failing test blocks the claim "done". Never dismiss one as unrelated without proof.

```bash
cd backend && uv run pytest --tb=short > "$SCRATCH/pytest.log" 2>&1
tail -n 40 "$SCRATCH/pytest.log"
```

A single failure is enough to stop. Before calling a failure pre-existing:

1. Run it in isolation: `uv run pytest tests/test_x.py::test_name -v`.
2. Check it passes on `origin/main`.
3. Only then document it and continue.

## Do not edit the test to make it pass

When a test fails, the default assumption is that the code is wrong, not the test.
Changing the test to match new behaviour needs explicit user permission first.

Legitimate reasons to change a test: the behaviour changed on purpose and the intent is
documented; the test asserted an implementation detail that no longer exists; the test was
non-deterministic and the fix is a better fixture, not a looser assertion.

Illegitimate, and the ones to watch for in yourself:

- "The test asserts X but my code produces Y, so I will assert Y." Your code may be wrong.
- "Loosening the assertion makes it pass." That hides a regression.
- "I will mark it `xfail` and move on." Not without user sign-off.

"Should I change the test or the code?" is a reasonable question to ask. Silently changing
the test is not.

## Especially here

The aggregation tests in the reports plan are golden tests against a seeded dataset. A
wrong total looks entirely plausible, so those tests are the only thing standing between a
bug and a purchasing decision made on bad numbers. Never loosen one to get green.
