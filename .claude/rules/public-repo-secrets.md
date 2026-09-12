# Public repository, real secrets

**Hard, non-negotiable.** This repository is public on GitHub. Anyone can read every file
and every commit in its history, forever. A secret that lands in a commit is compromised
the moment it is pushed, and deleting it later does not undo that: GitHub keeps orphaned
commits reachable by SHA.

## Never in a committed file

Connection strings, passwords, API keys, JWT secrets, the device-token pepper, session
cookies, `.env` in any form. Not in code, not in tests, not in a doc "as an example", not
commented out, not base64-encoded.

## Where configuration actually lives

| Value | Home |
|---|---|
| Real values | Render environment settings, entered through the dashboard |
| Names and shapes | `backend/.env.example`, placeholders only |
| Local development | `backend/.env`, gitignored, never committed |

`render.yaml` declares secret variables with `sync: false`, so Render prompts for them
and never stores them in the repository.

## Defences, in order

1. `.gitignore` covers `.env` and `.env.*` with an exception only for `.env.example`.
2. `gitleaks` runs as a pre-commit hook and again in CI.
3. GitHub secret scanning and push protection are enabled on the repository.
4. Generic high-entropy patterns are **not** covered by GitHub's provider patterns. The
   JWT secret and device pepper are just random strings, so `gitleaks` is the only thing
   that catches them. Do not disable the hook.

## Generating a secret

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the output into Render. Never into a file in this tree.

## If a secret is committed

Treat it as compromised, not as a mistake to hide.

1. Rotate the value first. Rewriting history does not un-leak it.
2. Then clean the history, and say so plainly in the PR.

## Frontend bundles

Anything shipped to the browser is public regardless of repository visibility. No key,
pepper, or connection string ever reaches `apps/pos` or `apps/admin`.
