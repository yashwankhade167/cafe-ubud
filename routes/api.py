"""
Cafe Ubud — Public REST API
=============================
Endpoints:
  GET  /api/menu                          -> menu items
  GET  /api/categories                    -> categories
  GET  /api/tables/<token>               -> resolve table QR token
  GET  /api/tables/<token>/qr.png        -> QR code image
  POST /api/orders                        -> place order
  GET  /api/orders/<id>                  -> fetch order status
  PATCH /api/orders/<id>/status          -> update status (emits WS event)
  POST /api/orders/<id>/payment/create   -> create Razorpay order
  POST /api/orders/<id>/payment/verify   -> verify payment & mark paid
  POST /api/reservations                 -> submit reservation
  POST /api/menu/<id>/image              -> upload menu item photo
  GET  /api/uploads/<filename>           -> serve uploaded images
"""

import io
import os
import uuid
import qrcode
from flask import (
    Blueprint, request, jsonify, send_file, url_for,
    current_app, send_from_directory
)
from models import db, MenuItem, Category, Table, Order, OrderItem, Reservation, ORDER_STATUSES
from services import (
    create_razorpay_order, verify_razorpay_signature,
    send_whatsapp, reservation_confirmation_message, order_ready_message
)
from app import socketio

api_bp = Blueprint("api", __name__)


def allowed_file(filename):
    exts = current_app.config.get("ALLOWED_EXTENSIONS", set())
    return "." in filename and filename.rsplit(".", 1)[1].lower() in exts


# ── MENU ──────────────────────────────────────────────────────────────
@api_bp.route("/menu", methods=["GET"])
def get_menu():
    category_slug = request.args.get("category")
    query = MenuItem.query.filter_by(is_available=True)
    if category_slug and category_slug != "all":
        category = Category.query.filter_by(slug=category_slug).first()
        if not category:
            return jsonify({"error": "Unknown category"}), 404
        query = query.filter_by(category_id=category.id)
    return jsonify([i.to_dict() for i in query.all()])


@api_bp.route("/categories", methods=["GET"])
def get_categories():
    return jsonify([c.to_dict() for c in Category.query.order_by(Category.sort_order).all()])


# ── IMAGE UPLOAD ──────────────────────────────────────────────────────
@api_bp.route("/menu/<int:item_id>/image", methods=["POST"])
def upload_menu_image(item_id):
    item = MenuItem.query.get_or_404(item_id)
    if "image" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["image"]
    if not file or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    file.save(os.path.join(upload_folder, filename))

    item.image_url = url_for("api.serve_upload", filename=filename, _external=False)
    db.session.commit()
    return jsonify({"image_url": item.image_url})


@api_bp.route("/uploads/<path:filename>")
def serve_upload(filename):
    import os
    from flask import send_from_directory, current_app, abort
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    file_path = os.path.join(upload_folder, filename)
    if not os.path.exists(file_path):
        abort(404)
    return send_from_directory(upload_folder, filename)

# ── TABLES / QR ───────────────────────────────────────────────────────
@api_bp.route("/tables/<token>", methods=["GET"])
def resolve_table(token):
    table = Table.query.filter_by(qr_token=token, is_active=True).first()
    if not table:
        return jsonify({"error": "Invalid or inactive table QR code"}), 404
    return jsonify(table.to_dict())


@api_bp.route("/tables/<token>/qr.png", methods=["GET"])
def table_qr_image(token):
    table = Table.query.filter_by(qr_token=token).first()
    if not table:
        return jsonify({"error": "Unknown table"}), 404

    order_url = url_for("public.table_order", token=token, _external=True)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10, border=3,
    )
    qr.add_data(order_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1A1208", back_color="#FAF6EF")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(
        buffer, mimetype="image/png",
        as_attachment=request.args.get("download") == "1",
        download_name=f"cafe-ubud-table-{table.number}-qr.png",
    )


# ── ORDERS ────────────────────────────────────────────────────────────
@api_bp.route("/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    items_payload = data.get("items", [])
    if not items_payload:
        return jsonify({"error": "Order must contain at least one item"}), 400

    table = None
    if data.get("table_token"):
        table = Table.query.filter_by(qr_token=data["table_token"], is_active=True).first()
        if not table:
            return jsonify({"error": "Invalid table token"}), 400

    order = Order(
        table_id=table.id if table else None,
        customer_name=data.get("customer_name", ""),
        customer_phone=data.get("customer_phone", ""),
        notes=data.get("notes", ""),
        status="pending",
    )
    db.session.add(order)
    db.session.flush()

    total = 0.0
    for entry in items_payload:
        menu_item = MenuItem.query.get(entry.get("menu_item_id"))
        qty = max(1, int(entry.get("quantity", 1)))
        if not menu_item:
            continue
        db.session.add(OrderItem(
            order_id=order.id, menu_item_id=menu_item.id,
            quantity=qty, price_at_order=menu_item.price,
        ))
        total += menu_item.price * qty

    order.total_amount = round(total, 2)
    db.session.commit()

    # Notify kitchen via WebSocket
    socketio.emit("new_order", order.to_dict(), room="kitchen")

    return jsonify(order.to_dict()), 201


@api_bp.route("/orders/<int:order_id>", methods=["GET"])
def get_order(order_id):
    return jsonify(Order.query.get_or_404(order_id).to_dict())


@api_bp.route("/orders/<int:order_id>/status", methods=["PATCH"])
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = (request.get_json(silent=True) or {}).get("status")
    if new_status not in ORDER_STATUSES:
        return jsonify({"error": f"Invalid status"}), 400
    order.status = new_status
    db.session.commit()

    # Push real-time update to the customer's table page
    socketio.emit("order_update", order.to_dict(), room=f"order_{order.id}")
    socketio.emit("order_update", order.to_dict(), room="kitchen")

    # WhatsApp when order is ready
    if new_status == "ready" and order.customer_phone:
        send_whatsapp(order.customer_phone, order_ready_message(order))

    return jsonify(order.to_dict())


# ── PAYMENTS (Razorpay) ───────────────────────────────────────────────
@api_bp.route("/orders/<int:order_id>/payment/create", methods=["POST"])
def create_payment(order_id):
    order = Order.query.get_or_404(order_id)
    if order.payment_status == "paid":
        return jsonify({"error": "Already paid"}), 400

    rz_order = create_razorpay_order(order.total_amount, receipt=f"order_{order.id}")
    if not rz_order:
        # Razorpay not configured — return a mock so the UI still works in dev
        return jsonify({
            "mock": True,
            "key_id": "rzp_test_demo",
            "razorpay_order_id": f"mock_{order.id}",
            "amount": int(order.total_amount * 100),
            "currency": "INR",
            "name": "Cafe Ubud",
            "description": f"Order #{order.id}",
        })

    order.razorpay_order_id = rz_order["id"]
    db.session.commit()

    return jsonify({
        "key_id": os.environ.get("RAZORPAY_KEY_ID"),
        "razorpay_order_id": rz_order["id"],
        "amount": rz_order["amount"],
        "currency": rz_order["currency"],
        "name": "Cafe Ubud",
        "description": f"Order #{order.id}",
    })


@api_bp.route("/orders/<int:order_id>/payment/verify", methods=["POST"])
def verify_payment(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.get_json(silent=True) or {}

    # Mock path — dev/demo without real Razorpay
    if data.get("mock"):
        order.payment_status = "paid"
        db.session.commit()
        socketio.emit("order_update", order.to_dict(), room=f"order_{order.id}")
        socketio.emit("order_update", order.to_dict(), room="kitchen")
        return jsonify({"paid": True, "mock": True})

    razorpay_order_id  = data.get("razorpay_order_id", "")
    razorpay_payment_id = data.get("razorpay_payment_id", "")
    razorpay_signature  = data.get("razorpay_signature", "")

    if not verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        return jsonify({"error": "Invalid payment signature"}), 400

    order.payment_status = "paid"
    order.razorpay_payment_id = razorpay_payment_id
    db.session.commit()

    socketio.emit("order_update", order.to_dict(), room=f"order_{order.id}")
    socketio.emit("order_update", order.to_dict(), room="kitchen")

    return jsonify({"paid": True})


# ── RESERVATIONS ──────────────────────────────────────────────────────
@api_bp.route("/reservations", methods=["POST"])
def create_reservation():
    data = request.get_json(silent=True) or {}
    required = ["name", "phone", "date", "time"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400

    reservation = Reservation(
        name=data["name"], phone=data["phone"],
        date=data["date"], time=data["time"],
        guests=int(data.get("guests", 2)),
        special_requests=data.get("special_requests", ""),
    )
    db.session.add(reservation)
    db.session.commit()

    # Send WhatsApp confirmation
    sent = send_whatsapp(data["phone"], reservation_confirmation_message(reservation))
    if sent:
        reservation.whatsapp_sent = True
        db.session.commit()

    return jsonify(reservation.to_dict()), 201


# ── WEBSOCKET ROOMS ───────────────────────────────────────────────────
from flask_socketio import join_room

@socketio.on("join_order")
def on_join_order(data):
    """Customer calls this after placing an order to receive live updates."""
    order_id = data.get("order_id")
    if order_id:
        join_room(f"order_{order_id}")

@socketio.on("join_kitchen")
def on_join_kitchen(data):
    """Admin kitchen display calls this to receive all order events."""
    join_room("kitchen")
