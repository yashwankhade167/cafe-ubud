"""
Cafe Ubud — Public Page Routes
=================================
Serves the customer-facing HTML pages: the main storefront and the
per-table QR ordering page.
"""

from flask import Blueprint, render_template, abort
from models import Table

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    """Main storefront — the cinematic Bali experience landing page."""
    return render_template("index.html")


@public_bp.route("/table/<token>")
def table_order(token):
    """
    The page a customer lands on after scanning their table's QR code.
    Resolves the token server-side so a bad/expired QR shows a clean 404
    instead of a broken ordering screen.
    """
    table = Table.query.filter_by(qr_token=token, is_active=True).first()
    if not table:
        abort(404)
    return render_template("table_order.html", table=table)
