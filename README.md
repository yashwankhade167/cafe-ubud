# Cafe Ubud — Flask Backend + Admin Dashboard

A complete Flask backend powering the Cafe Ubud Bali-experience website:
customer ordering, QR table ordering, live order tracking, reservations,
and a full admin dashboard for managing the café.

## What's included

- **Public storefront** (`/`) — the cinematic Bali-themed landing page, now wired
  to a live menu and working reservation form.
- **QR table ordering** (`/table/<token>`) — the page a customer lands on after
  scanning their table's QR code. Mobile-first, no login, instant ordering with
  a live status tracker.
- **REST API** (`/api/...`) — menu, categories, orders, reservations, table
  resolution.
- **Admin dashboard** (`/admin`) — session-login-protected panel with:
  - Revenue/orders/tables metrics
  - Live order management with status updates
  - Menu CRUD (add/edit/delete/hide items)
  - Inventory tracking with low-stock alerts
  - Reservation management
  - Table/QR code listing

## Project structure

```
cafe-ubud-backend/
├── app.py              # Flask app factory
├── run.py              # entry point (python run.py)
├── models.py           # SQLAlchemy models
├── seed.py             # populates the database with starter data
├── requirements.txt
├── routes/
│   ├── public.py       # storefront + table ordering page
│   ├── api.py          # JSON REST API
│   └── admin.py        # admin dashboard routes (session-auth)
├── templates/
│   ├── index.html              # main storefront
│   ├── table_order.html        # per-table QR ordering page
│   └── admin/                  # dashboard pages
└── instance/
    └── cafeubud.db      # SQLite database (created on first run)
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Seed the database (creates tables, menu, 12 café tables, admin login)
python seed.py

# 3. Run the server
python run.py
```

Visit:
- **Storefront** → http://127.0.0.1:5000/
- **Admin dashboard** → http://127.0.0.1:5000/admin/login

**Demo admin login:** `admin` / `ubud2026`

## Trying the QR ordering flow

After seeding, 12 tables exist with unique tokens, each with a **real, scannable
QR code** (no placeholder graphics — generated server-side with the `qrcode`
library). Go to the admin **Tables** page (`/admin/tables`) to see them, or
**Tables → Print All QR Codes** for a print-ready sheet sized for cutting out
and placing on physical tables.

| Endpoint | What it does |
|---|---|
| `/admin/tables` | Grid view — each table's QR image, with download buttons |
| `/admin/tables/print` | Clean print sheet, no sidebar, 3-per-row, dashed cut lines |
| `/api/tables/<token>/qr.png` | The raw PNG, generated on the fly from the table's full URL |
| `/api/tables/<token>/qr.png?download=1` | Same image, forces a file download with a clean filename |

The QR encodes the **full absolute URL** to that table's ordering page, so it
keeps working unchanged if you move from `localhost` to a real domain —
no regenerating images, just redeploy.

## API reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/menu?category=coffee` | List menu items, optional category filter |
| GET | `/api/categories` | List categories |
| GET | `/api/tables/<token>` | Resolve a QR token to a table |
| GET | `/api/tables/<token>/qr.png` | Scannable QR code image for that table |
| POST | `/api/orders` | Place an order |
| GET | `/api/orders/<id>` | Fetch order (used for live tracking) |
| PATCH | `/api/orders/<id>/status` | Update order status |
| POST | `/api/reservations` | Submit a table reservation |

Example order payload:
```json
{
  "table_token": "abc123",
  "customer_name": "Aarav",
  "items": [{ "menu_item_id": 1, "quantity": 2 }]
}
```

## Notes & next steps

This was built as a learning/portfolio project, so a few things are
intentionally simplified — worth knowing if you take it further:

- **SQLite** is used for zero-setup local development. For a real café,
  swap to PostgreSQL/MySQL by changing `SQLALCHEMY_DATABASE_URI` in `app.py`.
- **Admin auth** is simple session-based login — fine for one admin user.
  A multi-staff or public-facing product would want proper role-based access.
- **Payments** aren't integrated yet — `total_amount` is calculated and
  stored, but there's no Razorpay/UPI checkout flow wired up.
- **Order status updates** are pull-based (the table page polls every 5s).
  A production system would likely use WebSockets for instant push updates.
- Change `SECRET_KEY` and the admin password before any real deployment.

## Deploying to production

See **[DEPLOY.md](./DEPLOY.md)** for a complete step-by-step guide to
deploying on Render's free tier (live URL in ~5 minutes, no credit card).

The project ships with:
- `render.yaml` — Render service definition (auto-detected from repo root)
- `start.sh` — startup script (seeds DB + launches gunicorn)
- `requirements.txt` — includes gunicorn for production serving
- `.gitignore` — keeps the SQLite file and secrets out of git
