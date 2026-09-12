# FestivalApp

Drink-sales registration and analysis for a festival. Bar staff record orders on a tablet
in as few taps as possible; organisers get live figures during the event and purchasing
advice afterwards.

The point of the system is the dataset it leaves behind. Every edition's sales are kept, so
next year's stock order rests on what actually happened rather than on memory.

```
┌─ apps/pos    (Vue 3 PWA)  ──┐        ┌──────────────┐      ┌─────────────┐
│  bar tablets, offline-first │───────▶│  FastAPI     │─────▶│ MongoDB     │
└─────────────────────────────┘        │  (Render)    │      │ Atlas M0    │
┌─ apps/admin  (Vue 3 SPA)  ──┐        │              │      │             │
│  organiser: stats + config  │───────▶└──────────────┘      └─────────────┘
└─────────────────────────────┘
   both on Cloudflare Pages
```

Everything runs on free tiers.

## Status

| Part | State |
|---|---|
| Backend API | Built and tested |
| POS app (bar tablets) | Built, runs locally, not yet used at a festival |
| Admin app (organisers) | Built, runs locally |
| Hosting | **Not set up yet.** See [`docs/TODO.md`](docs/TODO.md) |

---

## Running it locally

You need [`uv`](https://docs.astral.sh/uv/) and Node 22. No Docker, no sudo, no accounts:
MongoDB is downloaded into a gitignored `.tools/` on first use.

```bash
make install install-web    # dependencies (downloads MongoDB the first time)
make mongo-start            # local database on port 27017
make seed-demo              # three editions of demo sales; prints device codes
make dev                    # API on :8000            ← leave running
make dev-pos                # bar app on :5173        ← second terminal
make dev-admin              # organiser app on :5174  ← third terminal
```

Then create an organiser login, once:

```bash
cd backend && uv run python -m app.cli create-organiser jij@voorbeeld.be
```

- **Bar app**: <http://localhost:5173>. Paste a code that `make seed-demo` printed, pick a
  name, start tapping.
- **Organiser app**: <http://localhost:5174>. Log in with the account you just made.

`make mongo-stop` shuts the database down. `make help` lists every target.

### Two kinds of seed data

| Command | What you get |
|---|---|
| `make seed` | One small festival. Good for trying the till |
| `make seed-demo` | Three editions with growth, a drink introduced mid-way, one falling out of favour, and a stockout. Use this to look at the reports |

`seed-demo` is deterministic: the same numbers every run.

### Testing on a real tablet

`make dev-pos` prints a `Network:` address such as `http://192.168.1.20:5173`. Open that on
a tablet on the same wifi. The API is proxied through the same address, so there is nothing
else to configure.

Add it to the home screen for the real thing: it installs as a PWA with no browser chrome,
which is how staff should run it.

### Checking that offline actually works

1. Sell something with the API running. The badge reads `opgeslagen`.
2. Stop the API with Ctrl-C. Keep selling. The badge counts up: `2 wachtend`.
3. Start the API again. Within five seconds the queue drains, the badge returns to
   `opgeslagen`, and nothing is duplicated.

---

## Deploying it

Follow [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) in order: Atlas, then Render, then two
Cloudflare Pages projects, then fix `CORS_ORIGINS`, then create your organiser account.
About half an hour, mostly waiting for builds.

[`docs/TODO.md`](docs/TODO.md) is the checklist of everything only you can do, including
what to configure before a festival and what to do on the day.

### After the free tiers are set up

Once Atlas, Render and Pages are live, the day-to-day looks like this.

**Configuring a new edition.** Everything happens in the organiser app under
**Instellingen**, in this order, because each step depends on the one before:

1. **Edities** — name, year, and *the value of one bonnetje in euros*. Every euro figure in
   the app derives from that number.
2. **Categorieën** — the rows on the tablet screen, in the order you want them. Colour comes
   from a fixed set of eight, chosen to stay distinguishable on a dark screen at night.
3. **Verkooppunten** — the bars.
4. **Dranken** — name, slug, category, price in bonnetjes, and, when the invoices arrive,
   the purchase price per single item plus how you buy it (a `bak` of 24, a `doos` of 6).
   Tick which bars sell it.
5. **Medewerkers** — the names staff pick from at the start of a shift.
6. **Tablets** — issue a code per tablet, like `K9GG-BBVY-MF0T`, and type it into the bar
   app. Codes are shown exactly once; **Nieuwe code** replaces a lost one and kills the old.

**Deploying a change.** Push to `main`. Render and both Pages projects rebuild
automatically. CI runs first; if it is red, nothing is deployed that you have to undo.

**During a festival.** Point a free cron at `/api/v1/health` every 10 minutes to keep the
backend awake, and **turn it off afterwards**: a permanently awake service burns 730 of the
750 free instance-hours a month. Details in
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md#keeping-the-backend-awake-on-festival-days).

**After a festival.** Enter the supplier invoices under **Instellingen → Dranken**. Every
historical margin report becomes correct at once, because cost is joined when a report runs
rather than frozen into each sale. Then read **Rapporten → Inkoopadvies**.

---

## What the apps do

### Bar app

A five-drink round is six taps: three on Jupiler, two on Water, one on the total. No
dialogs, no menus, no second screen.

| Action | Gesture |
|---|---|
| Add a drink | Tap the product |
| Remove one | Hold the product, or tap its chip in the strip |
| Commit | Tap the total bar. Clears instantly for the next customer |
| Undo | Tap `↶ ongedaan`. No confirmation |
| Empty the order | `leegmaken` |
| Staff drink (free) | `personeel` in the header, then commit as usual |
| Change staff member | Tap the name in the header |

It keeps selling through a total network outage. Orders are written to the tablet before
the screen clears and sync when signal returns; because the tablet generates each order's
id, a retry can never duplicate a sale.

### Organiser app

**Live** — consumpties, bonnetjes, omzet, marge, per drink, per bar, per staff member, and
sales per hour with a toggle between counts, revenue and margin, optionally split by drink.
Refreshes every 15 seconds.

**Rapporten** — profit per product, margin against volume, which drinks carry the volume,
hourly demand, busiest hour per bar, what staff drank, year-over-year comparison, and a
purchasing plan that ends in a shopping list with a total. Everything exports to CSV.

**Instellingen** — editions, categories, bars, drinks, staff, tablets.

---

## Development

```bash
make check      # what CI runs: lint, format check, backend tests
make test       # backend tests only
make test-web   # frontend tests
make lint       # fix what ruff can fix
```

End-to-end tests for the till need the stack running and a device code:

```bash
cd apps/pos && POS_DEVICE_TOKEN=<code from make seed> npm run e2e
```

They skip without the code, so they do not run in CI. Run them after touching the sell
screen.

Conventions live in [`CLAUDE.md`](CLAUDE.md) and [`.claude/rules/`](.claude/rules/). The
ones worth knowing before changing anything:

- [`sales-data-invariants`](.claude/rules/sales-data-invariants.md) — nine properties that
  keep the dataset trustworthy. Breaking one produces plausible wrong numbers rather than
  an error.
- [`public-repo-secrets`](.claude/rules/public-repo-secrets.md) — this repository is public.
- [`no-failing-tests`](.claude/rules/no-failing-tests.md) — read the exit code, not a grep
  of the output.

Design and plans are under [`docs/INDEX.md`](docs/INDEX.md).

## Security

This repository is public. No secret may ever be committed. Real values live in Render's
environment settings; `backend/.env.example` holds placeholders only.

`gitleaks` runs as a pre-commit hook and again in CI, and GitHub secret scanning with push
protection is enabled. Install the hooks before your first commit:

```bash
uv tool install pre-commit
pre-commit install
```

Device codes are twelve characters so they can be typed. That is sixty bits, which is only
safe because failed codes are rate limited per address; see
[`app/throttle.py`](backend/app/throttle.py).
