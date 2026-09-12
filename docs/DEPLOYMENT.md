# Deployment

Everything runs on free tiers. Nothing here costs money.

| Component | Provider | Plan | Notes |
|---|---|---|---|
| Database | MongoDB Atlas | M0 free | 512 MB, one free cluster per project |
| Backend API | Render | Free web service | 750 instance-hours/month, sleeps after 15 min idle |
| POS front-end | Cloudflare Pages | Free | Plan 2 |
| Admin front-end | Cloudflare Pages | Free | Plans 3 and 4 |

## The cold start, and why it does not matter

A free Render service sleeps after 15 minutes of inactivity and takes about a minute to
wake. Two things make that invisible in practice:

1. The front-ends are static files on Cloudflare Pages, which never sleeps. A tablet
   loads instantly even while the API is asleep.
2. The POS app is offline-first. It sells from local storage and syncs later, so it does
   not care whether the API is awake at the moment of a sale.

On festival days, keep the service warm with a free cron ping (cron-job.org or similar)
every 10 minutes against `/api/v1/health`. Do **not** leave that running all month: a
permanently awake service consumes about 730 of the 750 free instance-hours, leaving no
margin.

## First-time setup

### 1. MongoDB Atlas

1. Create a free **M0** cluster at https://cloud.mongodb.com in an EU region
   (`eu-west-1`, Ireland, is closest to Belgium).
2. **Database Access**: add a user `festival_app` with **Autogenerate Secure Password**.
   Save the password somewhere safe. Scope it to **Read and write** on the `festival`
   database only, not to any database.
3. **Network Access**: add `0.0.0.0/0`.

   Render's free tier has no fixed egress IP, so there is no narrower rule to write. The
   scoped user in step 2 is the compensating control: those credentials can reach one
   database and nothing else in the cluster. This is a real weakening and worth
   revisiting if the backend ever moves to a host with a static IP.
4. Copy the connection string.

### 2. Generate the secrets

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # DEVICE_TOKEN_PEPPER
```

Run it twice. The two values must differ. Paste them into Render only, never into a file
in this repository.

### 3. Render

Connect the repository at https://dashboard.render.com, choose **New**, then
**Blueprint**. `render.yaml` declares the service; Render prompts for the four variables
marked `sync: false`.

| Variable | Value |
|---|---|
| `MONGO_URI` | The Atlas connection string from step 1 |
| `JWT_SECRET` | First generated secret |
| `DEVICE_TOKEN_PEPPER` | Second generated secret |
| `CORS_ORIGINS` | JSON array of the front-end origins, e.g. `["https://pos-festival.pages.dev","https://admin-festival.pages.dev"]` |

`CORS_ORIGINS` must be a JSON array, and it must never contain `*`. There is a test
asserting the wildcard is absent. Update it once the real Pages URLs exist in plan 3.

### 4. Verify

```bash
curl -sS https://festival-api.onrender.com/api/v1/health
```

Expect `{"status":"ok"}`. If this is the first call in 15 minutes it takes about a
minute, which is the documented free-tier behaviour and not a fault.

### 5. Create your organiser account

There is no signup endpoint by design. Open a **Shell** on the Render service:

```bash
uv run python -m app.cli create-organiser you@example.com
```

It prompts twice for a password and requires at least 12 characters.

Then check login works:

```bash
curl -sS -X POST https://festival-api.onrender.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"<the password you set>"}' -i | head -20
```

Expect `200` and a `set-cookie: session=...; HttpOnly; Secure; SameSite=strict`.

## Environment variables

Names only. Values live in Render and nowhere else.

| Variable | Required | Set in `render.yaml` | Notes |
|---|---|---|---|
| `MONGO_URI` | yes | prompted | Atlas connection string |
| `MONGO_DB` | no | `festival` | Database name |
| `JWT_SECRET` | yes | prompted | At least 32 characters, enforced at startup |
| `DEVICE_TOKEN_PEPPER` | yes | prompted | At least 32 characters, must differ from `JWT_SECRET` |
| `CORS_ORIGINS` | yes | prompted | JSON array, never `*` |
| `ACCESS_TOKEN_TTL_MINUTES` | no | `720` | Organiser session length |
| `COOKIE_SECURE` | no | `true` | Only `false` for local HTTP development |
| `PYTHON_VERSION` | no | `3.12.10` | Matches `backend/.python-version` and CI |

The app refuses to start if a required secret is missing or shorter than 32 characters,
so a misconfigured deploy fails loudly instead of running with a weak key.

## Rotating a secret

**`JWT_SECRET`**: change it in Render and redeploy. Every organiser is logged out and
logs back in. No data is affected.

**`DEVICE_TOKEN_PEPPER`**: this one is destructive. Device tokens are stored as
`HMAC(token, pepper)`, so changing the pepper invalidates **every enrolled tablet at
once**. They all have to be re-enrolled from the admin app. Never do this during a
festival. If a single tablet is lost, revoke that device instead:

```
POST /api/v1/admin/devices/{id}/revoke
```

**`MONGO_URI`**: rotate the password in Atlas, update Render, redeploy.

## If a secret is committed

Treat it as compromised, not as a mistake to tidy away. Rotate the value first, because
rewriting git history does not un-leak it: GitHub keeps orphaned commits reachable by
their full SHA. Clean the history second, and say so plainly in the PR.
