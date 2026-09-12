# FestivalApp

Drink-sales registration and analysis for a festival. Bar staff record orders on a tablet
in as few taps as possible; organisers get live figures during the event and purchasing
advice afterwards.

The point of the system is the dataset it leaves behind. Every edition's sales are kept,
so next year's stock order can be based on what actually happened rather than on memory.

## Status

| Part | State |
|---|---|
| Backend API | Built and tested |
| POS app (bar tablets) | Built and testable locally |
| Admin app (organisers) | Not started, plans 3 and 4 |

## Documentation

- [Design](docs/superpowers/specs/2026-09-12-festival-sales-app-design.md) covers the data
  model, the API, and the reasoning behind each decision.
- [Documentation index](docs/INDEX.md) lists the plans and harness notes.
- [Deployment](docs/DEPLOYMENT.md) covers Atlas, Render, and secret rotation.

## Running the whole thing locally

Five commands. The first is a one-off.

```bash
make install install-web    # dependencies (downloads MongoDB on first run)
make mongo-start            # local database on port 27017
make seed                   # demo festival; prints a device token per bar
make dev                    # the API on :8000       (leave this running)
make dev-pos                # the POS app on :5173   (second terminal)
```

Open http://localhost:5173, paste one of the tokens `make seed` printed, pick a name, and
start tapping. `make mongo-stop` shuts the database down again.

### Testing on a real tablet

`make dev-pos` prints a `Network:` address such as `http://192.168.1.20:5173`. Open that
on a tablet on the same wifi. The API is proxied through the same address, so there is
nothing else to configure.

Add it to the home screen for the real experience: it installs as a PWA with no browser
chrome, which is how staff should run it.

### Checking that offline actually works

1. Sell something with the API running. The badge reads `opgeslagen`.
2. Stop the API with Ctrl-C. Keep selling. The badge counts up: `2 wachtend`.
3. Start the API again. Within five seconds the queue drains, the badge returns to
   `opgeslagen`, and nothing is duplicated.

## Backend development

Requires `uv`. Tests run against a real MongoDB, which is downloaded into a gitignored
`.tools/` on first use. Docker and sudo are not needed.

```bash
make install    # install dependencies
make test       # run the test suite
make dev        # run the API with auto-reload
make check      # everything CI runs
make help       # all targets
```

Interactive API docs at http://127.0.0.1:8000/docs once `make dev` is running.

To point at a database, copy `backend/.env.example` to `backend/.env` and fill it in.
That file is gitignored.

## Architecture

Two Vue front-ends over one FastAPI backend and one MongoDB database. The POS app is an
offline-first PWA: it keeps selling through a total network outage and syncs when signal
returns. That works because each tablet generates its own order IDs, which makes syncing
idempotent, so a retry over a flaky link can never duplicate a sale.

Everything runs on free tiers: Cloudflare Pages for the front-ends, Render for the API,
MongoDB Atlas M0 for the database.

## Security

This repository is public. No secret may ever be committed. Real values live in Render's
environment settings; `backend/.env.example` holds placeholders only.

`gitleaks` runs as a pre-commit hook and again in CI, and GitHub secret scanning with push
protection is enabled. Install the hooks before your first commit:

```bash
uv tool install pre-commit
pre-commit install
```

See [`.claude/rules/public-repo-secrets.md`](.claude/rules/public-repo-secrets.md).
