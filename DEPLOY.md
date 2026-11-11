# Deploying Cafe Ubud to Render (Free Tier)

Your site will be live at `https://cafe-ubud.onrender.com` (or similar)
in about 5 minutes. Follow these steps exactly.

---

## Step 1 — Push your code to GitHub

If you haven't already, create a GitHub account at https://github.com

Then create a new repository:

1. Go to https://github.com/new
2. Name it `cafe-ubud` (or anything you like)
3. Leave it **Public** (required for Render free tier)
4. Click **Create repository**

Now push your project from your computer. Open a terminal in the
`cafe-ubud-backend` folder and run:

```bash
git init
git add .
git commit -m "Initial commit — Cafe Ubud backend"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/cafe-ubud.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

---

## Step 2 — Create a Render account

Go to https://render.com and sign up (free, no credit card needed).
Sign in with your GitHub account — this lets Render access your repo.

---

## Step 3 — Create a new Web Service

1. On the Render dashboard, click **New +** → **Web Service**
2. Connect your GitHub account if prompted
3. Find and select your `cafe-ubud` repository
4. Click **Connect**

---

## Step 4 — Configure the service

Render will auto-detect `render.yaml` in your repo and fill most fields.
Confirm these settings:

| Field | Value |
|---|---|
| Name | cafe-ubud |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `bash start.sh` |
| Instance Type | **Free** |

Under **Environment Variables**, Render will auto-generate `SECRET_KEY`
from `render.yaml` — no action needed.

Click **Create Web Service**.

---

## Step 5 — Watch it deploy

Render will:
1. Clone your repo
2. Run `pip install -r requirements.txt`
3. Run `bash start.sh` which seeds the database then starts gunicorn

Watch the build log — it takes about 2–3 minutes on first deploy.
You'll see:

```
Seeding database...
Database seeded successfully.
Starting gunicorn...
[INFO] Listening at: http://0.0.0.0:10000
```

Once you see **Live** (green dot), your site is public. ✅

---

## Step 6 — Open your live site

Render gives you a URL like:
```
https://cafe-ubud.onrender.com
```

| Page | URL |
|---|---|
| Storefront | `https://cafe-ubud.onrender.com/` |
| Admin login | `https://cafe-ubud.onrender.com/admin/login` |
| Admin dashboard | `https://cafe-ubud.onrender.com/admin/dashboard` |
| Table 1 ordering | `https://cafe-ubud.onrender.com/table/<token>` (get from admin Tables page) |

**Admin login:** `admin` / `ubud2026`
⚠️ Change the password immediately in `seed.py` before going live.

---

## Redeploying after changes

Every time you push to GitHub, Render auto-redeploys:

```bash
# Make your changes, then:
git add .
git commit -m "Update menu prices"
git push
```

Render picks it up in seconds and rebuilds.

---

## Important notes for free tier

- **Sleep after 15 min inactivity** — the free tier spins down after
  15 minutes of no traffic. First visit after sleep takes ~30 seconds
  to wake up. This is normal.
- **SQLite resets on each deploy** — Render's free tier has an ephemeral
  filesystem, so `start.sh` re-seeds the database on every boot. Orders
  and reservations placed by real customers will be lost on redeploy.
  To fix this, upgrade to a Render PostgreSQL database (free tier available)
  and update `DATABASE_URL` — just say the word and I'll set it up.
- **Custom domain** — you can add your own domain (e.g. `cafeubud.in`)
  in the Render dashboard under **Settings → Custom Domains** for free.

---

## Troubleshooting

**Build fails on `pip install`**
→ Check that `requirements.txt` is committed to your repo root.

**Site loads but shows an error**
→ Open Render dashboard → your service → **Logs** tab to see the error.

**Admin login doesn't work**
→ The seed script ran with the wrong password — check `seed.py` line
  that sets `admin.set_password(...)`.

**QR codes show wrong domain**
→ Render auto-detects the host from the request, so QR codes will
  correctly encode your `onrender.com` URL on first scan. If you add
  a custom domain, the QR will encode that domain for any scan made
  through it.
