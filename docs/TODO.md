# What is left for you

Everything here needs an account, a decision, or a real festival. Nothing in this list
blocks local development: the whole system runs on your laptop today.

Last updated 2026-09-12.

---

## 1. Blocking, before the app can be used at a festival

### 1.1 Create the MongoDB Atlas cluster

Free forever, no card. Roughly ten minutes. Full walkthrough in
[`DEPLOYMENT.md`](DEPLOYMENT.md#1-mongodb-atlas).

At the end of it you need the connection string. Nothing else in this list can be done
without it.

### 1.2 Deploy the backend to Render

Free, no card. `render.yaml` in the repository root already describes the service, so
Render only asks for the four secret values. Walkthrough in
[`DEPLOYMENT.md`](DEPLOYMENT.md#3-render).

### 1.3 Deploy both front-ends to Cloudflare Pages

Two projects from the same repository, different build commands. Walkthrough in
[`DEPLOYMENT.md`](DEPLOYMENT.md#4-cloudflare-pages).

**After this one, come back and update `CORS_ORIGINS` on Render** with the real Pages URLs,
then redeploy. The apps cannot talk to the API until you do; this is the step most likely
to be forgotten.

### 1.4 Create your organiser account

There is no signup page by design. One command in the Render shell:

```bash
uv run python -m app.cli create-organiser jij@voorbeeld.be
```

### 1.5 Decide what a bonnetje is worth in euros

Set it per edition under **Instellingen → Edities**. Until it is right, every euro figure
in the app is wrong: omzet, marge, and the total on the purchasing advice all derive from
it. It is the single most consequential number you will type.

---

## 2. Needed before the festival, not before the deploy

### 2.1 The real drinks list

`make seed` invents an assortment. Replace it under **Instellingen → Dranken**:

| Field | Why it matters |
|---|---|
| Naam | What staff sees on the button |
| Slug | The identity that survives across years. Set it once, never change it |
| Categorie | Which row the button sits in |
| Bonnetjes | The selling price |
| Inkoopprijs | Per single item, not per crate. Drives every margin figure |
| Verpakking + stuks | How you buy it. Drives the purchasing advice and the restant column |
| Beschikbaar bij | Which bars sell it |

Inkoopprijs can wait for the invoices. Everything else cannot.

### 2.2 Categories, in the order you want them on screen

**Instellingen → Categorieën**. The order here is the order of the rows on the tablets, so
put whatever sells fastest at the top. Colours come from a fixed set of eight, chosen
because they stay distinguishable on a dark screen at night.

### 2.3 Bars and staff names

**Instellingen → Verkooppunten** and **→ Medewerkers**. Staff pick their own name at the
start of a shift, so the list needs to be complete before doors open.

### 2.4 Enrol the tablets

**Instellingen → Tablets** issues a code like `K9GG-BBVY-MF0T`. Type it into the bar app
once per tablet. Codes are shown exactly once; if one is lost, press **Nieuwe code** and
the old one stops working immediately.

Do this at home on wifi, not at the gate.

### 2.5 App icons

The PWA manifest ships with no icons, so a tablet's home screen shows a blank square. Any
512×512 and 192×192 PNG will do. Drop them in `apps/pos/public/` and add them to the
`icons` array in `apps/pos/vite.config.ts`, or send me the artwork and I will wire it up.

---

## 3. Worth doing on the day

### 3.1 Keep the backend awake

Render's free tier sleeps after 15 minutes of inactivity and takes about a minute to wake.
The tablets do not care, because they sell offline and sync afterwards, but the organiser
dashboard will feel slow on its first load.

On festival days, point a free cron ping (cron-job.org) at
`https://<your-service>.onrender.com/api/v1/health` every 10 minutes.

**Turn it off afterwards.** A permanently awake service burns about 730 of the 750 free
instance-hours in a month, leaving no margin.

### 3.2 Do one real round on a tablet before doors open

Sell something, check it appears on the live dashboard within 15 seconds, then undo it.
That single loop proves the tablet, the code, the network and the backend all work.

---

## 4. After the festival

### 4.1 Enter the supplier invoices

**Instellingen → Dranken**, inkoopprijs per product. Every historical margin report becomes
correct the moment you do, because cost is joined when a report runs rather than frozen
into each sale.

Until then, products without a cost price show a dash rather than a made-up margin, and
the reports say how many are missing.

### 4.2 Read the purchasing advice with the restant column open

The advice rounds up to whole packs. **Restant** is what that rounding leaves you holding,
which for something like coffee bought in boxes of 100 can be most of a box.

Products marked **was op** ran out. Their sales figure measures what was in stock, not what
people wanted, so they carry a 25% buffer instead of 10%.

---

## 5. Open questions for you

1. **Is six taps right for a five-drink round**, or should a single drink be one tap? A
   one-tap path is possible but adds a mode, and modes get left on.
2. **Does the order strip earn its space**, or would you rather have more grid?
3. **Should undo reach further back than the last order?** It is single-level today.
4. **Does the margin-volume quadrant earn its place**, or would a plain table do?
5. **Waste analysis**: if you record what you bought and what was left over, the app can
   show bought vs sold vs leftover in euros. Worth building?

---

## 6. Known gaps I have not built

Listed so their absence is not mistaken for an oversight.

- **Reassigning an order to a different staff member** after the fact. The spec mentions
  it; no endpoint exists and nobody has needed it.
- **The last-ten-orders undo list.** Single-level undo covers the common mis-tap.
- **Stockout marking from the tablet.** The backend accepts it and the reports use it, but
  the POS has no `OP!` gesture yet: it needs settling on real hardware first.
- **Waste analysis.** See question 5.
- **A second organiser account with limited rights.** Everyone who logs in can change
  everything.
