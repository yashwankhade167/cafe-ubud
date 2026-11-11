"""
Cafe Ubud — Admin Dashboard Routes
"""

import io
import os
import base64
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from models import (
    db, AdminUser, Order, OrderItem, MenuItem, Category,
    Table, Reservation, InventoryItem, ORDER_STATUSES
)
from services import (
    send_whatsapp, reservation_confirmation_message
)
from app import socketio

admin_bp = Blueprint("admin", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped


# ── AUTH ──────────────────────────────────────────────────────────────
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = AdminUser.query.filter_by(username=request.form.get("username", "")).first()
        if user and user.check_password(request.form.get("password", "")):
            session["admin_id"] = user.id
            session["admin_username"] = user.username
            return redirect(url_for("admin.dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


# ── DASHBOARD ─────────────────────────────────────────────────────────
@admin_bp.route("/")
@admin_bp.route("/dashboard")
@login_required
def dashboard():
    today = datetime.utcnow().date()
    today_orders = Order.query.filter(db.func.date(Order.created_at) == str(today)).all()

    revenue_today = sum(o.total_amount for o in today_orders)
    orders_today  = len(today_orders)
    active_tables = Order.query.filter(
        Order.status.notin_(["completed", "cancelled"]),
        Order.table_id.isnot(None)
    ).distinct(Order.table_id).count()
    avg_order_value = round(revenue_today / orders_today, 2) if orders_today else 0

    top_items = (
        db.session.query(MenuItem.name, MenuItem.emoji, db.func.sum(OrderItem.quantity).label("sold"))
        .join(OrderItem, OrderItem.menu_item_id == MenuItem.id)
        .group_by(MenuItem.id).order_by(db.desc("sold")).limit(5).all()
    )

    low_stock = InventoryItem.query.filter(
        InventoryItem.quantity <= InventoryItem.low_stock_threshold
    ).all()

    pending_reservations = Reservation.query.filter_by(status="pending").count()

    # Revenue last 7 days for sparkline chart
    revenue_7d = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        day_orders = Order.query.filter(db.func.date(Order.created_at) == str(d)).all()
        revenue_7d.append({"day": d.strftime("%a"), "revenue": round(sum(o.total_amount for o in day_orders), 2)})

    return render_template(
        "admin/dashboard.html",
        revenue_today=revenue_today,
        orders_today=orders_today,
        active_tables=active_tables,
        avg_order_value=avg_order_value,
        top_items=top_items,
        low_stock=low_stock,
        pending_reservations=pending_reservations,
        revenue_7d=revenue_7d,
    )


# ── ORDER MANAGEMENT ─────────────────────────────────────────────────
@admin_bp.route("/orders")
@login_required
def orders():
    status_filter = request.args.get("status", "all")
    query = Order.query.order_by(Order.created_at.desc())
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    return render_template(
        "admin/orders.html",
        orders=query.limit(100).all(),
        statuses=ORDER_STATUSES,
        current_filter=status_filter,
    )


@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@login_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get("status")
    if new_status in ORDER_STATUSES:
        order.status = new_status
        db.session.commit()
        # Emit real-time update to customer
        socketio.emit("order_update", order.to_dict(), room=f"order_{order.id}")
        socketio.emit("order_update", order.to_dict(), room="kitchen")
        # WhatsApp when ready
        if new_status == "ready" and order.customer_phone:
            from services import order_ready_message
            send_whatsapp(order.customer_phone, order_ready_message(order))
    return redirect(url_for("admin.orders"))


# ── MENU MANAGEMENT ───────────────────────────────────────────────────
@admin_bp.route("/menu")
@login_required
def menu():
    return render_template(
        "admin/menu.html",
        items=MenuItem.query.order_by(MenuItem.category_id).all(),
        categories=Category.query.order_by(Category.sort_order).all(),
    )


@admin_bp.route("/menu/add", methods=["POST"])
@login_required
def add_menu_item():
    category_id = request.form.get("category_id")
    if not category_id:
        flash("Please select a category.", "error")
        return redirect(url_for("admin.menu"))

    item = MenuItem(
        name=request.form.get("name"),
        description=request.form.get("description", ""),
        price=float(request.form.get("price", 0)),
        emoji=request.form.get("emoji", "🍽️"),
        tag=request.form.get("tag", ""),
        category_id=int(category_id),
        is_available=True,
    )
    db.session.add(item)
    db.session.flush()

    # Handle optional image upload at creation time
    file = request.files.get("image")
    if file and file.filename:
        from routes.api import allowed_file
        import uuid
        from flask import current_app
        if allowed_file(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
            item.image_url = url_for("api.serve_upload", filename=filename)

    db.session.commit()
    flash(f'"{item.name}" added.', "success")
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/<int:item_id>/edit", methods=["POST"])
@login_required
def edit_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    item.name        = request.form.get("name", item.name)
    item.description = request.form.get("description", item.description)
    item.price       = float(request.form.get("price", item.price))
    item.emoji       = request.form.get("emoji", item.emoji)
    item.tag         = request.form.get("tag", item.tag)
    item.category_id = int(request.form.get("category_id", item.category_id))

    file = request.files.get("image")
    if file and file.filename:
        from routes.api import allowed_file
        import uuid
        from flask import current_app
        if allowed_file(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
            item.image_url = url_for("api.serve_upload", filename=filename)

    db.session.commit()
    flash(f'"{item.name}" updated.', "success")
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    item.is_available = not item.is_available
    db.session.commit()
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    # Detach any order items referencing this menu item before deleting
    # so existing order history is preserved but the link is cleared
    from models import OrderItem
    OrderItem.query.filter_by(menu_item_id=item.id).update({"menu_item_id": None})
    db.session.delete(item)
    db.session.commit()
    flash(f'"{item.name}" removed.', "success")
    return redirect(url_for("admin.menu"))


# ── INVENTORY ─────────────────────────────────────────────────────────
@admin_bp.route("/inventory")
@login_required
def inventory():
    return render_template(
        "admin/inventory.html",
        items=InventoryItem.query.order_by(InventoryItem.name).all(),
    )


@admin_bp.route("/inventory/add", methods=["POST"])
@login_required
def add_inventory_item():
    db.session.add(InventoryItem(
        name=request.form.get("name"),
        unit=request.form.get("unit", "kg"),
        quantity=float(request.form.get("quantity", 0)),
        low_stock_threshold=float(request.form.get("low_stock_threshold", 5)),
    ))
    db.session.commit()
    flash("Item added.", "success")
    return redirect(url_for("admin.inventory"))


@admin_bp.route("/inventory/<int:item_id>/update", methods=["POST"])
@login_required
def update_inventory_item(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    item.quantity = float(request.form.get("quantity", item.quantity))
    db.session.commit()
    return redirect(url_for("admin.inventory"))


# ── RESERVATIONS ──────────────────────────────────────────────────────
@admin_bp.route("/reservations")
@login_required
def reservations():
    return render_template(
        "admin/reservations.html",
        reservations=Reservation.query.order_by(Reservation.created_at.desc()).all(),
    )


@admin_bp.route("/reservations/<int:res_id>/status", methods=["POST"])
@login_required
def update_reservation_status(res_id):
    res = Reservation.query.get_or_404(res_id)
    new_status = request.form.get("status")
    if new_status in ("pending", "confirmed", "cancelled"):
        res.status = new_status
        db.session.commit()
        # Send WhatsApp on confirmation
        if new_status == "confirmed" and not res.whatsapp_sent:
            sent = send_whatsapp(res.phone, reservation_confirmation_message(res))
            if sent:
                res.whatsapp_sent = True
                db.session.commit()
                flash("Reservation confirmed & WhatsApp sent.", "success")
    return redirect(url_for("admin.reservations"))


# ── TABLES ────────────────────────────────────────────────────────────
@admin_bp.route("/tables")
@login_required
def tables():
    return render_template(
        "admin/tables.html",
        tables=Table.query.order_by(Table.number).all(),
    )


@admin_bp.route("/tables/print")
@login_required
def tables_print():
    return render_template(
        "admin/tables_print.html",
        tables=Table.query.order_by(Table.number).all(),
    )


# ── REVENUE CHART API (for dashboard) ────────────────────────────────
@admin_bp.route("/api/revenue-chart")
@login_required
def revenue_chart():
    """Returns a base64 PNG of the last 30 days revenue chart."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    today = datetime.utcnow().date()
    days, revenues = [], []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        day_orders = Order.query.filter(db.func.date(Order.created_at) == str(d)).all()
        days.append(d.strftime("%d %b"))
        revenues.append(round(sum(o.total_amount for o in day_orders), 2))

    fig, ax = plt.subplots(figsize=(10, 3))
    fig.patch.set_facecolor("#211A10")
    ax.set_facecolor("#211A10")
    ax.plot(days, revenues, color="#C9A84C", linewidth=2, marker="o", markersize=4)
    ax.fill_between(range(len(days)), revenues, alpha=0.15, color="#C9A84C")
    ax.set_xticks(range(0, len(days), 5))
    ax.set_xticklabels([days[i] for i in range(0, len(days), 5)], color="#888", fontsize=8)
    ax.tick_params(axis="y", colors="#888", labelsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:.0f}"))
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    ax.grid(axis="y", color="#333", linestyle="--", linewidth=0.5)
    plt.tight_layout(pad=0.5)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor="#211A10")
    plt.close(fig)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode()
    return jsonify({"chart": f"data:image/png;base64,{img_b64}"})
