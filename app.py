import os
import json
import sqlite3
from datetime import datetime
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, abort

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "invoice.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
SETTINGS_FILE = os.path.join(BASE_DIR, "company_profile.json")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            invoice_date TEXT NOT NULL,
            due_date TEXT,
            bill_to_name TEXT NOT NULL,
            bill_to_email TEXT,
            bill_to_address TEXT,
            currency TEXT NOT NULL DEFAULT 'INR',
            notes TEXT,
            terms TEXT,
            subtotal REAL NOT NULL DEFAULT 0,
            tax_rate REAL NOT NULL DEFAULT 0,
            tax_amount REAL NOT NULL DEFAULT 0,
            discount REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Unpaid',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL DEFAULT 0,
            line_total REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    conn.close()


def load_company_profile():
    if not os.path.exists(SETTINGS_FILE):
        return {
            "company_name": "",
            "tagline": "",
            "email": "",
            "phone": "",
            "website": "",
            "tax_id_label": "GSTIN",
            "tax_id_value": "",
            "address": "",
            "bank_details": "",
            "default_tax_rate": 0,
            "default_notes": "Thank you for your business.",
            "default_terms": "Payment due within 7 days.",
            "accent_color": "#1f4bd8",
            "logo_filename": ""
        }
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_company_profile(profile):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


def save_logo(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
        raise ValueError("Unsupported logo format. Use PNG, JPG, JPEG, WEBP, or SVG.")
    filename = f"logo_{uuid4().hex}{ext}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file_storage.save(path)
    return filename


def next_invoice_number():
    conn = get_db()
    row = conn.execute(
        "SELECT invoice_number FROM invoices ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return "INV-0001"
    value = row["invoice_number"]
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits:
        n = int(digits) + 1
        return f"INV-{n:04d}"
    return f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"


@app.template_filter("money")
def money_filter(value):
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return value


@app.route("/")
def home():
    conn = get_db()
    invoices = conn.execute(
        "SELECT id, invoice_number, bill_to_name, invoice_date, due_date, total, status FROM invoices ORDER BY id DESC"
    ).fetchall()
    conn.close()
    company = load_company_profile()
    stats = {
        "count": len(invoices),
        "unpaid_total": sum(float(i["total"]) for i in invoices if i["status"] != "Paid"),
        "paid_total": sum(float(i["total"]) for i in invoices if i["status"] == "Paid"),
    }
    return render_template("index.html", invoices=invoices, company=company, stats=stats)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    profile = load_company_profile()
    if request.method == "POST":
        profile["company_name"] = request.form.get("company_name", "").strip()
        profile["tagline"] = request.form.get("tagline", "").strip()
        profile["email"] = request.form.get("email", "").strip()
        profile["phone"] = request.form.get("phone", "").strip()
        profile["website"] = request.form.get("website", "").strip()
        profile["tax_id_label"] = request.form.get("tax_id_label", "GSTIN").strip() or "GSTIN"
        profile["tax_id_value"] = request.form.get("tax_id_value", "").strip()
        profile["address"] = request.form.get("address", "").strip()
        profile["bank_details"] = request.form.get("bank_details", "").strip()
        profile["default_notes"] = request.form.get("default_notes", "").strip()
        profile["default_terms"] = request.form.get("default_terms", "").strip()
        profile["accent_color"] = request.form.get("accent_color", "#1f4bd8").strip() or "#1f4bd8"

        logo = request.files.get("logo")
        if logo and logo.filename:
            try:
                profile["logo_filename"] = save_logo(logo)
            except ValueError as e:
                flash(str(e), "error")
                return render_template("settings.html", company=profile), 400

        save_company_profile(profile)
        flash("Company profile updated.", "success")
        return redirect(url_for("settings"))

    return render_template("settings.html", company=profile)


@app.route("/invoice/new", methods=["GET", "POST"])
def new_invoice():
    company = load_company_profile()
    if request.method == "POST":
        invoice_number = request.form.get("invoice_number", "").strip() or next_invoice_number()
        invoice_date = request.form.get("invoice_date", "").strip() or datetime.now().strftime("%Y-%m-%d")
        due_date = request.form.get("due_date", "").strip()
        bill_to_name = request.form.get("bill_to_name", "").strip()
        bill_to_email = request.form.get("bill_to_email", "").strip()
        bill_to_address = request.form.get("bill_to_address", "").strip()
        currency = request.form.get("currency", "INR").strip() or "INR"
        notes = request.form.get("notes", "").strip()
        terms = request.form.get("terms", "").strip()
        status = request.form.get("status", "Unpaid").strip() or "Unpaid"
        tax_rate = 0.0
        discount = 0.0

        descriptions = request.form.getlist("item_description[]")
        quantities = request.form.getlist("item_quantity[]")
        unit_prices = request.form.getlist("item_unit_price[]")

        items = []
        subtotal = 0.0
        for desc, qty, price in zip(descriptions, quantities, unit_prices):
            desc = desc.strip()
            if not desc:
                continue
            qty_val = float(qty or 0)
            price_val = float(price or 0)
            line_total = qty_val * price_val
            subtotal += line_total
            items.append(
                {
                    "description": desc,
                    "quantity": qty_val,
                    "unit_price": price_val,
                    "line_total": line_total,
                }
            )

        if not bill_to_name:
            flash("Client name is required.", "error")
            return render_template("invoice_form.html", company=company, invoice_number=invoice_number)

        if not items:
            flash("Add at least one invoice item.", "error")
            return render_template("invoice_form.html", company=company, invoice_number=invoice_number)

        tax_amount = 0.0
        total = subtotal

        now = datetime.now().isoformat(timespec="seconds")
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO invoices (
                    invoice_number, invoice_date, due_date, bill_to_name, bill_to_email,
                    bill_to_address, currency, notes, terms, subtotal, tax_rate, tax_amount,
                    discount, total, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_number, invoice_date, due_date, bill_to_name, bill_to_email,
                    bill_to_address, currency, notes, terms, subtotal, tax_rate, tax_amount,
                    discount, total, status, now, now
                )
            )
            invoice_id = cur.lastrowid
            for item in items:
                cur.execute(
                    """
                    INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, line_total)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_id, item["description"], item["quantity"],
                        item["unit_price"], item["line_total"]
                    )
                )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("Invoice number already exists. Please use another invoice number.", "error")
            return render_template("invoice_form.html", company=company, invoice_number=invoice_number)
        finally:
            conn.close()

        flash("Invoice created successfully.", "success")
        return redirect(url_for("view_invoice", invoice_id=invoice_id))

    return render_template(
        "invoice_form.html",
        company=company,
        invoice_number=next_invoice_number(),
        today=datetime.now().strftime("%Y-%m-%d")
    )


@app.route("/invoice/<int:invoice_id>")
def view_invoice(invoice_id):
    conn = get_db()
    invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not invoice:
        conn.close()
        abort(404)
    items = conn.execute(
        "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id ASC", (invoice_id,)
    ).fetchall()
    conn.close()
    company = load_company_profile()
    return render_template("invoice_view.html", invoice=invoice, items=items, company=company)


@app.route("/invoice/<int:invoice_id>/status", methods=["POST"])
def update_status(invoice_id):
    status = request.form.get("status", "Unpaid").strip() or "Unpaid"
    conn = get_db()
    conn.execute(
        "UPDATE invoices SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(timespec="seconds"), invoice_id)
    )
    conn.commit()
    conn.close()
    flash("Invoice status updated.", "success")
    return redirect(url_for("view_invoice", invoice_id=invoice_id))


@app.route("/invoice/<int:invoice_id>/delete", methods=["POST"])
def delete_invoice(invoice_id):
    conn = get_db()
    conn.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
    conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()
    flash("Invoice deleted.", "success")
    return redirect(url_for("home"))


@app.route("/api/preview", methods=["POST"])
def preview_invoice():
    data = request.get_json(force=True)
    tax_rate = 0.0
    discount = 0.0
    items = data.get("items", [])
    subtotal = 0.0
    normalized_items = []
    for item in items:
        desc = str(item.get("description", "")).strip()
        if not desc:
            continue
        qty = float(item.get("quantity", 0) or 0)
        price = float(item.get("unit_price", 0) or 0)
        line_total = qty * price
        subtotal += line_total
        normalized_items.append({
            "description": desc,
            "quantity": qty,
            "unit_price": price,
            "line_total": line_total
        })
    tax_amount = 0.0
    total = subtotal
    return jsonify({
        "items": normalized_items,
        "subtotal": round(subtotal, 2),
        "tax_amount": round(tax_amount, 2),
        "total": round(total, 2),
        "discount": round(discount, 2),
        "tax_rate": tax_rate
    })


@app.route("/health")
def health():
    return {"status": "ok", "service": "invoice-app"}


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
