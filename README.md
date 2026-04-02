# Invoice Tool

A branded invoice generator built with Flask, SQLite, HTML, CSS, and JavaScript.

## Features
- Company setup page with logo upload
- Accent color and invoice branding
- Invoice creation with dynamic line items
- Auto subtotal and total calculation
- Invoice history dashboard
- Status tracking: Unpaid, Paid, Partially Paid, Overdue
- Printable invoice page for "Print / Save as PDF"
- Ready to deploy on Render

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -c "from app import init_db; init_db()"
python app.py
```

Open http://127.0.0.1:5000

## Deploy on Render

1. Push this folder to a GitHub repo.
2. Go to Render and create a new Web Service from the repo.
3. Render will auto-detect `render.yaml`, or use:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python -c "from app import init_db; init_db()" && gunicorn app:app`
4. Add a persistent disk if you want uploaded logos and the SQLite database to survive redeploys.
5. For production scale, migrate from SQLite to PostgreSQL.

## Best invoice-template features this app already covers
- Branding with logo
- Professional clean layout
- Simple auto totals without tax or discount
- Reusable company defaults
- Invoice tracking
- PDF-ready print styling
