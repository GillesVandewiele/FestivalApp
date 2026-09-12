# Never keep work in the scratchpad

**Hard rule.** Source, scripts, docs, plans, and anything else you would be sad to lose go
straight to the repository and get committed. The session scratchpad and `/tmp` are for
regenerable command output only.

## The one question

**"If this file vanished, would I lose work, or just re-run a command?"**

| Loses work → repository, committed | Regenerable → scratchpad is fine |
|---|---|
| Source files | pytest, build, lint logs |
| Scripts (seeds, migrations, benchmarks) | `curl` response dumps, `openapi.json` |
| Design docs, plans, notes | `grep`/`find` captures |
| Anything you will reference again | Intermediate data you can re-derive |

The token-frugal guidance in `CLAUDE.md` — redirect chatty output to the scratchpad and
grep it — is about the right-hand column only.

## How to apply

- Write new files **straight to their repository path**, never to the scratchpad "to move
  later". There is no later that survives a reboot.
- If a throwaway file turns out to be worth keeping, move it into the repository and
  commit it in the same session.
