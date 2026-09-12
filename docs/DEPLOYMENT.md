# Deployment

Everything runs on free tiers. Nothing here costs money, and only Cloudflare asks for a
card (it does not charge one).

| Component | Provider | Plan | Notes |
|---|---|---|---|
| Database | MongoDB Atlas | M0 free | 512 MB, one free cluster per project |
| Backend API | Render | Free web service | 750 instance-hours/month, sleeps after 15 min idle |
| POS front-end | Cloudflare Pages | Free | Unlimited bandwidth, never sleeps |
| Admin front-end | Cloudflare Pages | Free | Second project, same repository |

Work through the sections in order. The whole thing takes about half an hour, most of it
waiting for builds.

## The cold start, and why it does not matter

A free Render service sleeps after 15 minutes of inactivity and takes about a minute to
wake. Two things make that invisible in practice:

1. The front-ends are static files on Cloudflare Pages, which never sleeps. A tablet loads
   instantly even while the API is asleep.
2. The POS app is offline-first. It sells from local storage and syncs later, so it does
   not care whether the API is awake at the moment of a sale.

The organiser dashboard is the only thing that feels it. See
[keeping it awake](#keeping-the-backend-awake-on-festival-days).

---

## 1. MongoDB Atlas

1. Sign up at <https://cloud.mongodb.com>. No card.
2. **Create a cluster**: choose **M0 Free**, provider AWS, region **eu-west-1 (Ireland)**.
   That is the closest free region to Belgium. Name it `festival`.
3. **Database Access** → *Add New Database User*:
   - Username `festival_app`
   - Password: **Autogenerate Secure Password**, then *Copy*. Save it somewhere safe now;
     Atlas will not show it again.
   - Under *Database User Privileges* choose **Specific Privileges**: `readWrite` on
     database `festival`. Not "any database".
4. **Network Access** → *Add IP Address* → **Allow access from anywhere** (`0.0.0.0/0`).

   Render's free tier has no fixed egress IP, so there is no narrower rule available. The
   scoped user in step 3 is what compensates: those credentials can reach one database and
   nothing else in the cluster. This is a genuine weakening, and worth revisiting if the
   backend ever moves somewhere with a static IP.
5. **Connect** → *Drivers* → copy the connection string. It looks like:

   ```
   mongodb+srv://festival_app:<password>@festival.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```

   Replace `<password>` with the one you saved. If the password contains `@`, `/`, `:` or
   `#`, URL-encode it or regenerate a simpler one.

## 2. Generate the two secrets

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # DEVICE_TOKEN_PEPPER
```

Run it **twice**; the two values must differ. Paste them into Render only, never into a
file in this repository. See [`.claude/rules/public-repo-secrets.md`](../.claude/rules/public-repo-secrets.md).

## 3. Render

1. Sign up at <https://dashboard.render.com> with your GitHub account. No card.
2. **New** → **Blueprint** → select `GillesVandewiele/FestivalApp`.
   `render.yaml` in the repository root describes the service, so Render only asks for the
   values marked `sync: false`:

   | Variable | Value |
   |---|---|
   | `MONGO_URI` | The Atlas connection string from step 1.5 |
   | `JWT_SECRET` | First generated secret |
   | `DEVICE_TOKEN_PEPPER` | Second generated secret |
   | `CORS_ORIGINS` | `["https://festival-bar.pages.dev","https://festival-beheer.pages.dev"]` |

   Use those two placeholder URLs for now. Section 4 tells you when to correct them.

   `CORS_ORIGINS` must be a **JSON array of strings**, and must never contain `*`. There is
   a test asserting the wildcard is absent.
3. Wait for the first deploy, then check it:

   ```bash
   curl -sS https://<your-service>.onrender.com/api/v1/health
   ```

   Expect `{"status":"ok"}`. The first call after an idle period takes about a minute; that
   is the documented free-tier behaviour, not a fault.

## 4. Cloudflare Pages

Two projects from the same repository. Sign up at <https://dash.cloudflare.com>; Pages
needs a card on file but does not charge it on the free plan.

### The POS app

**Workers & Pages** → **Create** → **Pages** → **Connect to Git** → this repository.

| Setting | Value |
|---|---|
| Project name | `festival-bar` |
| Production branch | `main` |
| Build command | `npm ci && npm run build --workspace apps/pos` |
| Build output directory | `apps/pos/dist` |
| Root directory | *(leave empty)* |

Under **Environment variables**, add:

| Name | Value |
|---|---|
| `VITE_API_BASE` | `https://<your-service>.onrender.com` |
| `NODE_VERSION` | `22` |

`VITE_API_BASE` is baked into the bundle at build time, so **changing it later needs a
rebuild**, not just a save.

### The admin app

Same again, with:

| Setting | Value |
|---|---|
| Project name | `festival-beheer` |
| Build command | `npm ci && npm run build --workspace apps/admin` |
| Build output directory | `apps/admin/dist` |

Same two environment variables.

### Then fix CORS

Both projects now have real URLs, something like `https://festival-bar.pages.dev`. Go back
to Render → your service → **Environment**, set `CORS_ORIGINS` to those two real URLs as a
JSON array, and **Save**, which redeploys.

**Skipping this is the most common way to end up with a deployment that looks fine and
does nothing.** The apps load, the API is up, and every request fails in the browser
console with a CORS error.

### Single-page routing

The admin app uses client-side routing, so a refresh on `/reports` must not 404.
`apps/admin/public/_redirects` already handles this and Cloudflare picks it up
automatically:

```
/*    /index.html   200
```

Nothing to do; it is noted here so the file is not mistaken for clutter.

## 5. Create your organiser account

There is no signup page by design. In the Render dashboard, open your service → **Shell**:

```bash
uv run python -m app.cli create-organiser jij@voorbeeld.be
```

It asks for a password twice and requires at least 12 characters.

Verify:

```bash
curl -sS -X POST https://<your-service>.onrender.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"jij@voorbeeld.be","password":"<the password>"}' -i | head -20
```

Expect `200` and `set-cookie: session=...; HttpOnly; Secure; SameSite=strict`.

## 6. Set the festival up

Open the admin app and work through
[`TODO.md` section 2](TODO.md#2-needed-before-the-festival-not-before-the-deploy):
edition and coupon value, categories, drinks, bars, staff, then enrol the tablets.

---

## Keeping the backend awake on festival days

Free instance-hours are 750 a month and a calendar month is about 730 hours, so a
permanently awake service leaves you 20 hours of margin. Do not leave a keep-alive running
all month.

On festival days only, point a free cron at the health endpoint every 10 minutes:

1. <https://cron-job.org>, free, no card.
2. URL `https://<your-service>.onrender.com/api/v1/health`, every 10 minutes.
3. **Disable it the day after.**

## Environment variables

Names only. Values live in Render and nowhere else.

| Variable | Required | Default in `render.yaml` | Notes |
|---|---|---|---|
| `MONGO_URI` | yes | prompted | Atlas connection string |
| `MONGO_DB` | no | `festival` | Database name |
| `JWT_SECRET` | yes | prompted | At least 32 characters, enforced at startup |
| `DEVICE_TOKEN_PEPPER` | yes | prompted | At least 32 characters, must differ from `JWT_SECRET` |
| `CORS_ORIGINS` | yes | prompted | JSON array of front-end origins, never `*` |
| `ACCESS_TOKEN_TTL_MINUTES` | no | `720` | Organiser session length |
| `COOKIE_SECURE` | no | `true` | Only `false` for local HTTP development |
| `PYTHON_VERSION` | no | `3.12.10` | Matches `backend/.python-version` and CI |

The app refuses to start if a required secret is missing or shorter than 32 characters, so
a misconfigured deploy fails loudly rather than running with a weak key.

Front-end builds take one variable, `VITE_API_BASE`, which is compiled into the bundle.

## Rotating a secret

**`JWT_SECRET`** — change it in Render and redeploy. Every organiser is logged out and logs
back in. No data is affected.

**`DEVICE_TOKEN_PEPPER`** — destructive. Device codes are stored as `HMAC(code, pepper)`, so
changing it invalidates **every enrolled tablet at once** and they all need re-enrolling.
Never during a festival. For one lost tablet, press **Nieuwe code** on that device in
**Instellingen → Tablets** instead, which kills only that code.

**`MONGO_URI`** — rotate the password in Atlas, update Render, redeploy.

## If a secret is committed

Treat it as compromised, not as a mistake to hide.

1. **Rotate the value first.** Rewriting git history does not un-leak it: GitHub keeps
   orphaned commits reachable by their full SHA.
2. Clean the history second, and say so plainly in the PR.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Apps load, every request fails in the console with a CORS error | `CORS_ORIGINS` still holds the placeholder URLs. Section 4, "Then fix CORS" |
| First request of the day takes a minute | Render woke from sleep. Expected |
| Tablet says "Koppelen mislukt" | Wrong code, or `VITE_API_BASE` points somewhere unreachable |
| Tablet says the code is refused after several tries | The guess throttle blocked that address for five minutes. Wait it out |
| Refreshing `/reports` gives a 404 | `apps/admin/public/_redirects` did not reach the build output |
| Backend will not start, logs mention validation | A secret is missing or under 32 characters |
| Everything worked, now the service is suspended | 750 free instance-hours exhausted. Turn off any keep-alive cron |
